# Hasty Paste
A fork of a fast and minimal paste bin, with encrypting pastes and corrected documentation.

## Features
- Optional encryption
- Quickly paste and save, to share some text
- Publicly accessible, no auth needed
- Randomly generated id's, optional "long" id to reduce brute force attacks
- Add expiring pastes
- Dark theme
- Optional syntax highlighting
- No JavaScript needed
- Uses minimal resources
- REST API
- Pick your file system
  - Custom flat-file system
  - :construction: S3 objects
- Caching (Internal & Redis)
- Lightweight Docker image (uses Alpine Linux)

## Showcase
[![Showcase Image](docs/assets/showcase.png)](docs/assets/showcase.png)

## Docs
Docs are located in the [/docs](docs/index.md) directory. Or on the site: [enchantedcode.co.uk/hasty-paste](https://enchantedcode.co.uk/hasty-paste)

## Hastily Paste It CLI
This is a simple script allowing the creation of pastes from the command-line. You can download your version [here](hastily-paste-it/README.md).

## Branches
| Name         | Description            | State         |
| :----------- | :--------------------- | :------------ |
| main         | Work ready for release | Stable        |
| next         | Work for next version  | Very Unstable |
| historical-X | Historical versions    | Unsupported   |

> Choose a tag/release for most stable if running project

## Why Is It Called "Hasty Paste"?
The name was chosen not because the project is written badly, but because you use it so fast without a care in the world and "Fast Paste" was already taken!

## License
This project is Copyright (c) 2024 Leo Spratt, licences shown below:

Code

    AGPL-3 or any later version. Full license found in `LICENSE.txt`

Documentation

    FDLv1.3 or any later version. Full license found in `docs/LICENSE.txt`
