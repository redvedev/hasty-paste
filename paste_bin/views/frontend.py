import logging

from quart import (Blueprint, abort, make_response, redirect, render_template,
                   request, url_for)
from quart_schema import hide

from ..config import get_settings
from ..core import helpers, renderer
from ..core.conversion import (form_field_to_datetime, local_to_utc,
                               utc_to_local)
from ..core.helpers import PasteHandlerException
from ..core.models import PasteMetaToCreate
from ..core.paste_handler import get_handler

#from cryptography.aes import AES
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from time import sleep # it's important sleep, to protect from brute-force attack
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding, hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os

blueprint = Blueprint("front_end", __name__)

logger = logging.getLogger("paste_bin")


@blueprint.get("/")
@hide
async def get_index():
    if get_settings().NEW_AT_INDEX:
        return await get_new_paste()
    return await render_template("index.jinja")


@blueprint.get("/about")
@hide
async def get_about():
    return await render_template("about.jinja")


@blueprint.get("/favicon.ico")
@hide
async def get_favicon():
    return redirect(url_for("static", filename="icon.svg"), 301)

def derive_key(password, salt, key_length=32):
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=key_length,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    return kdf.derive(password.encode())

def encrypt_paste(paste_content, password):
    # Generate a random salt and derive a key
    salt = os.urandom(16)
    key = derive_key(password, salt)
    
    # Generate a random IV
    iv = os.urandom(16)
    
    # Create the cipher object
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    
    # Pad the content and encrypt it
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded_data = padder.update(paste_content) + padder.finalize()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    
    # Return salt + IV + ciphertext
    encrypted_paste = salt + iv + ciphertext
    return encrypted_paste

# Function to decrypt the paste
def decrypt_paste(encrypted_paste_content, password):
    # Extract salt, IV, and ciphertext
    salt = encrypted_paste_content[:16]
    iv = encrypted_paste_content[16:32]
    ciphertext = encrypted_paste_content[32:]
    
    # Derive the key using the same salt
    key = derive_key(password, salt)
    
    # Create the cipher object
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    
    # Decrypt and unpad the content
    padded_data = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    paste_content = unpadder.update(padded_data) + unpadder.finalize()
    return paste_content

@blueprint.get("/new")
@hide
async def get_new_paste():
    default_settings = get_settings().UI_DEFAULT
    default_expires_at = None
    content = ""

    if (expiry := helpers.make_default_expires_at(default_settings.EXPIRE_TIME)) is not None:
        # NOTE ensure client has it in their timezone, not server's
        expiry = utc_to_local(expiry, get_settings().TIME_ZONE)
        default_expires_at = expiry.isoformat(timespec="minutes")

    # allow paste to be cloned for editing as new paste
    if (paste_id := request.args.get("clone_from")) is not None:
        paste_handler = get_handler()
        try:
            if (meta := await paste_handler.get_paste_meta(paste_id)) is not None:
                if meta.is_expired:
                    await paste_handler.remove_paste(paste_id)
                    abort(404)
                if (raw := await paste_handler.get_paste_raw(paste_id)) is not None:
                    content = raw.decode()
        except PasteHandlerException:
            # skip clone, if handler encounted an error
            logger.exception("cloning paste encounted an error")
            pass

    return await render_template(
        "new.jinja",
        default_expires_at=default_expires_at,
        get_highlighter_names=renderer.get_highlighter_names,
        content=content,
    )


@blueprint.post("/new")
@hide
async def post_new_paste():
    form = await request.form

    paste_content = (form["paste-content"].replace("\r\n", "\n")).encode()
    expires_at = form.get("expires-at", None, form_field_to_datetime)
    password = str(form.get("password"))
    if expires_at:
        # NOTE ensure client's timezone is converted to server's
        expires_at = local_to_utc(expires_at, get_settings().TIME_ZONE)
    lexer_name = form.get("highlighter-name", None)
    title = form.get("title", "", str).strip()
    if len(title) > 32:
        abort(400)
    title = None if title == "" else title

    if lexer_name == "":
        lexer_name = None

    if lexer_name and not renderer.is_valid_lexer_name(lexer_name):
        abort(400)

    password_hash = ""
    if len(password) > 0:
        ph = PasswordHasher()
        password_hash = ph.hash(password)
        paste_content = encrypt_paste(paste_content, password)
    paste_handler = get_handler()
    paste_settings = PasteMetaToCreate(
            expire_dt=expires_at,
            lexer_name=lexer_name,
            title=title,
            password_hash=password_hash
        )
    paste_id = await paste_handler.create_paste(
        get_settings().USE_LONG_ID,
        paste_content,
        paste_settings,
    )

    return redirect(url_for(".get_view_paste", paste_id=paste_id))

@blueprint.get("/<id:paste_id>", defaults={"override_lexer": None})
@blueprint.get("/<id:paste_id>.<override_lexer>")
@hide
@helpers.handle_known_exceptions
async def get_view_paste(paste_id: str, override_lexer: str | None):
    paste_handler = get_handler()
    paste_meta = await paste_handler.get_paste_meta(paste_id)

    if paste_meta is None:
        abort(404)
    if paste_meta.is_expired:
        await paste_handler.remove_paste(paste_id)
        abort(404)

    if len(paste_meta.password_hash) > 0: # the paste is encrypted, request password
        return await get_password_page(paste_meta, first_attempt=True)

    rendered_paste = await paste_handler.get_paste_rendered(paste_id, override_lexer)

    if rendered_paste is None:
        abort(500)

    return await render_template(
            "view.jinja",
            paste_content = rendered_paste,
            meta = paste_meta,
            paste_id_padded=helpers.padd_str(paste_id, "-", 5),
            )

async def get_password_page(paste_meta, first_attempt):
    return await render_template(
            "submit_password.jinja",
            meta = paste_meta,
            first_attempt = first_attempt # in next attempts show notification about wrong password
            )

@blueprint.post("/decrypt/<id:paste_id>", defaults={"override_lexer": None})
@blueprint.post("/decrypt/<id:paste_id>.<override_lexer>")
async def get_decrypted_paste(paste_id: str, override_lexer: str | None):
    form = await request.form
    password = str(form.get("password"))
    paste_handler = get_handler()
    paste_meta = await paste_handler.get_paste_meta(paste_id)
    ph = PasswordHasher()
    try:
        ph.verify(paste_meta.password_hash, password)
    except VerifyMismatchError:
        sleep(5) # prevent brute-force attacks, one attempt per 5 seconds
        return await get_password_page(paste_meta, first_attempt=False)

    rendered_paste = await paste_handler.get_paste_raw(paste_id)
    paste_content = decrypt_paste(rendered_paste, password).decode()
    lexer_name = paste_meta.lexer_name or "text"
    rendered = await renderer.highlight_content_async_wrapped(
            paste_content,
            lexer_name
            )

    if rendered_paste is None:
        abort(500)

    return await render_template(
            "view.jinja",
            paste_content = rendered,
            meta = paste_meta,
            paste_id_padded=helpers.padd_str(paste_id, "-", 5),
            )

@blueprint.get("/<id:paste_id>/raw")
@hide
@helpers.handle_known_exceptions
async def get_raw_paste(paste_id: str):
    paste_handler = get_handler()

    paste_meta = await paste_handler.get_paste_meta(paste_id)

    if paste_meta is None:
        abort(404)
    if paste_meta.is_expired:
        await paste_handler.remove_paste(paste_id)
        abort(404)

    raw_paste = await paste_handler.get_paste_raw(paste_id)

    if raw_paste is None:
        abort(500)

    response = await make_response(raw_paste)
    response.mimetype = "text/plain"

    return response
