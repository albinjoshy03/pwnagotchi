import json
import logging
import os

import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK


class GPSDaemon(plugins.Plugin):
    __author__ = "fheylis (https://github.com/fheylis)"
    __version__ = "1.0.0"
    __license__ = "GPL3"
    __description__ = "Save GPS coordinates from GPSD whenever a handshake is captured."

    def __init__(self):
        self.running = False
        self.coordinates = None

    def on_loaded(self):
        logging.info(f"[gpsdaemon] plugin loaded for {self.options['host']}:{self.options['port']}")

    def on_ready(self, agent):
        logging.info(f"[gpsdaemon] enabling bettercap's gpsdaemon module for {self.options['host']}:{self.options['port']}")

        agent.run(f"set gpsdaemon.host {self.options['host']}")
        agent.run(f"set gpsdaemon.port {self.options['port']}")
        agent.run("gpsdaemon on")
        self.running = True

    def on_handshake(self, agent, filename, access_point, client_station):
        if self.running:
            info = agent.session()
            self.coordinates = info["gps"]
            gps_filename = filename.replace(".pcap", ".gps.json")

            logging.info(f"[gpsdaemon] saving GPS to {gps_filename} ({self.coordinates})")
            with open(gps_filename, "w+t") as fp:
                json.dump(self.coordinates, fp)

    def on_ui_setup(self, ui):
        # add coordinates for other displays
        if ui.is_waveshare_v2():
            lat_pos = (127, 75)
            lon_pos = (122, 84)
            alt_pos = (127, 94)
        elif ui.is_waveshare_v1():
            lat_pos = (130, 70)
            lon_pos = (125, 80)
            alt_pos = (130, 90)
        elif ui.is_inky():
            # guessed values, add tested ones if you can
            lat_pos = (112, 30)
            lon_pos = (112, 49)
            alt_pos = (87, 63)
        elif ui.is_waveshare144lcd():
            # guessed values, add tested ones if you can
            lat_pos = (67, 73)
            lon_pos = (62, 83)
            alt_pos = (67, 93)
        else:
            # guessed values, add tested ones if you can
            lat_pos = (127, 51)
            lon_pos = (127, 56)
            alt_pos = (102, 71)

        label_spacing = 0

        ui.add_element(
            "latitude",
            LabeledValue(
                color=BLACK,
                label="lat:",
                value="-",
                position=lat_pos,
                label_font=fonts.Small,
                text_font=fonts.Small,
                label_spacing=label_spacing,
            ),
        )
        ui.add_element(
            "longitude",
            LabeledValue(
                color=BLACK,
                label="long:",
                value="-",
                position=lon_pos,
                label_font=fonts.Small,
                text_font=fonts.Small,
                label_spacing=label_spacing,
            ),
        )
        ui.add_element(
            "altitude",
            LabeledValue(
                color=BLACK,
                label="alt:",
                value="-",
                position=alt_pos,
                label_font=fonts.Small,
                text_font=fonts.Small,
                label_spacing=label_spacing,
            ),
        )


    def on_unload(self, ui):
        with ui._lock:
            ui.remove_element('latitude')
            ui.remove_element('longitude')
            ui.remove_element('altitude')


    def on_ui_update(self, ui):
        if self.coordinates and all([
            # avoid 0.000... measurements
            self.coordinates["Latitude"], self.coordinates["Longitude"]
        ]):
            # last char is sometimes not completely drawn
            # using an ending-whitespace as workaround on each line
            ui.set("latitude", f"{self.coordinates['Latitude']:.4f} ")
            ui.set("longitude", f" {self.coordinates['Longitude']:.4f} ")
            ui.set("altitude", f" {self.coordinates['Altitude']:.1f}m ")
