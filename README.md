# CalendarMaker

This is a utility script to build and publish a calendar based on configuration.

## Preparation of Python Environment

To use this script, you'll need to run it with python 3.9 or higher
and with the nostr, requests and bech32 packages installed.

First, create a virtual environment (or activate a common one)

```sh
python3 -m venv ~/.pyenv/calendarmaker
source ~/.pyenv/calendarmaker/bin/activate
```

Then install the dependencies
```sh
python3 -m pip install nostr@git+https://github.com/vicariousdrama/python-nostr.git
python3 -m pip install requests
python3 -m pip install bech32
```

## Configuration

### Identity Config File

A configuration file named `config.json` is required and takes the following form:

```json
{
    "nsec": "nsec....",
    "relays": [
        {"url":"wss://nostr.pleb.network","read":true,"write":true},
        {"url":"wss://nostr-pub.wellorder.net","read":true,"write":true},
        {"url":"wss://nostr.mom","read":true,"write":true},
        {"url":"wss://relay.nostr.bg","read":true,"write":true}
    ],
}
```

For convenience, you can start with the sample-config.json

```sh
cp sample-config.json config.json
```

The name of the config file can be overridden using the `--config` parameter when calling the script.

The `nsec` should be the identity of the user that should create/own the calendar. This can be your primary nsec as a user, or a different one. If you dont provide a value, a new private key will be created and nsec stored back in config file.

The `relays` list should contain a list of relays to connect and read calendars and events from, and which to write the resulting calendar to.

### Calendar Config File

A configure file named `caledarconfig.json` needs to be presented which takes the following form:

```json
{
    "frequency": 14400,
    "searchlist": [
      {"kind": 31924, "author": "90cca4db5ad5a9359d88ed8a6710df461d73a7e51b02e633016aefc05b130ac6", "d": "a3e6a7c8"},
      {"kind": 31923, "author": "21b419102da8fc0ba90484aec934bf55b7abcf75eedb39124e8d75e491f41a5e", "phrase": "bitcoin"},
      {"kind": 31923, "author": "1eb5d2c90ae0b1c07105d29c3861f5c36c0245aee8b09196339e6c25ee9e8d5f", "phrase": "bitcoin"},
      {"kind": 31923, "author": "a136247d8caf7e30bf403d32006faeca0c9d1cec7a16075e4142c2fed6cade60", "phrase": "bitcoin"}
    ],
    "name": "My Calendar",
    "content": "A description for this calendar",
    "description": "A description for this calendar",
    "uuid.comment": "Leave the following field empty. It will get populated",
    "uuid": "",
    "image.comment": "You can include a url to an image for your calendar",
    "image": "https://thewealthmastery.io/wp-content/uploads/2023/02/what-is-nostr-768x402.jpg"
}
```

For convenience, you can start with the sample-config.json

```sh
cp sample-calendarconfig.json calendarconfig.json
```

The name of the calendar config file can be overridden using the `--calendar` parameter when calling the script.


The `frequency` field is how often the calendar should be rebuilt when run as a background process.  Setting this value to 0 will run once and exit.

The `searchlist` is an array. The kind value for each item can be either another calendar (31924), for which all events will be added with the `d` tag value (matches the calendar uuid), or date (31922) or time (31923) events published by the referenced author.  The `phrase`` will be compared in a case insensitive way to any returned events against the event content, or tags for the name or description.

The `name` field is the name for the calendar

The `content` field is what is used by Flockstr.com for the short description.

The `description` field may be superfluous. Flockstr creates for its calendars but doesnt seem to use, and is nonstandard and otherwise a duplicate of the content.

The `uuid` should be a universally unique identifier per calendar. This is assumed to be unique per pubkey for indexing, but not verified. Flockstr uses short 8 character hexadecimal (4 byte) values.  If you leave this value blank, it will be assigned automatically on the first run, so that it remains consistent for that calendar configuration.

The `image` is used as the calendar image and banner. Flockstr supports multiple images. The ratio for images for banner format is 10:4 or else it will be truncated.  

## Running

Once configured, to run the script simply execute the following which will use the virtual python environment referenced.

change to the folder where calendarmaker.py is

```sh
~/.pyenv/calendarmaker/bin/python calendarmaker.py
```

You may override the main config file or the calendar config file using paraters as follows:

```sh
~/.pyenv/calendarmaker/bin/python calendarmaker.py --config path/to/customconfig.json --calendar calendar-tvshows.json
```