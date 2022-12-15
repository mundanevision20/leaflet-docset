# leaflet-docset

Documentation for the [Leaflet](https://leafletjs.com/) JavaScript map library in the Dash [docset](https://kapeli.com/docsets) format, ready for offline reading and searching.

## How to use the docset

### To download the original docset (v1.4)

1. Install a docset viewer, like [Dash](https://kapeli.com/dash) or [Zeal](https://zealdocs.org/).
2. In Dash's preferences, search for this docset under the "user contributed"
3. Press "download"

### To download the latest docset (v1.8.0)

Please download the docset file (`Leaflet.tgz`) from the latest [release](https://github.com/mundanevision20/leaflet-docset/releases).

## How to generate the docset

The docs are copied from the Leaflet site and indexed using a Python script. To set up and run the Python script:

```bash
   cd leaflet-docset
   virtualenv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python __init__.py
```

## Copyright

This is a complete rewrite and update of the original Ruby generator script created by Drew Dara-Abrams (2013-2019).
Please also see the LICENSE file.
