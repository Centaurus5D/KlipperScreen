import contextlib
import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Pango
from ks_includes.KlippyGcodes import KlippyGcodes
from ks_includes.screen_panel import ScreenPanel
from ks_includes.widgets.bedmap import BedMap


class Panel(ScreenPanel):

    def __init__(self, screen, title):
        title = title or _("5D Module Calibrate")
        super().__init__(screen, title)
        self.show_create = False
        self.active_mesh = None
        section = self._printer.get_config_section("bed_mesh")
        self.mesh_radius = section['mesh_radius'] if 'mesh_radius' in section else None
        self.profiles = {}
        self.buttons = {
            'calib': self._gtk.Button("refresh", _("Calibrate"), "color3", self.bts, Gtk.PositionType.LEFT, 1),
            'clear': self._gtk.Button("cancel", _("Clear"), "color2", self.bts, Gtk.PositionType.LEFT, 1),
        }
        self.buttons['clear'].connect("clicked", self.send_clear_wcs)
        self.buttons['calib'].connect("clicked", self.tool_calibrate)

        topbar = Gtk.Box(spacing=5, hexpand=True, vexpand=False)

        topbar.add(self.buttons['clear'])
        topbar.add(self.buttons['calib'])

        self.load_wcs()

        grid = Gtk.Grid(column_homogeneous=True)
        grid.attach(topbar, 0, 0, 2, 1)
        self.labels['map'] = self._gtk.Image("wcs-graph", self._gtk.content_width, self._gtk.content_height * .9)
        if self._screen.vertical_mode:
            grid.attach(self.labels['map'], 0, 2, 2, 1)

        else:
            grid.attach(self.labels['map'], 0, 2, 1, 1)
        self.labels['main_grid'] = grid
        self.content.add(self.labels['main_grid'])

    def activate(self):
        self.load_wcs()


    def retrieve_bm(self, profile):
        if profile is None:
            return None
        if profile == self.active_mesh:
            return self._printer.get_stat("bed_mesh")
        else:
            return self._printer.get_config_section(f"bed_mesh {profile}")

    def update_graph(self, widget=None, profile=None):
        if self.ks_printer_cfg is not None:
            invert_x = self._config.get_config()['main'].getboolean("invert_x", False)
            invert_y = self._config.get_config()['main'].getboolean("invert_y", False)
            rotation = self.ks_printer_cfg.getint("screw_rotation", 0)
            if rotation not in (0, 90, 180, 270):
                rotation = 0

            logging.info(f"Inversion X: {invert_x} Y: {invert_y} Rotation: {rotation}")

    def add_profile(self, profile):
        logging.debug(f"Adding Profile: {profile}")
        name = self._gtk.Button(label=f"<big><b>{profile}</b></big>")
        name.get_children()[0].set_use_markup(True)
        name.get_children()[0].set_line_wrap(True)
        name.get_children()[0].set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        name.set_vexpand(False)
        name.set_halign(Gtk.Align.START)

        name.connect("clicked", self.update_graph, profile)

        buttons = {
            "save": self._gtk.Button("complete", None, "color4", self.bts),
            "delete": self._gtk.Button("cancel", None, "color2", self.bts),
        }
        buttons["save"].connect("clicked", self.send_save_mesh, profile)
        buttons["delete"].connect("clicked", self.send_remove_mesh, profile)

        for b in buttons.values():
            b.set_hexpand(False)
            b.set_vexpand(False)
            b.set_halign(Gtk.Align.END)

        button_box = Gtk.Box(spacing=5)
        if profile != "default":
            button_box.add(buttons["save"])
        button_box.add(buttons["delete"])

        box = Gtk.Box(spacing=5)
        box.get_style_context().add_class("frame-item")
        box.pack_start(name, True, True, 0)
        box.pack_start(button_box, False, False, 0)

        self.profiles[profile] = {
            "name": name,
            "button_box": button_box,
            "row": box,
            "save": buttons["save"],
            "delete": buttons["delete"],
        }

        pos = self._get_position(profile)
        self.labels['profiles'].insert_row(pos)
        self.labels['profiles'].attach(self.profiles[profile]['row'], 0, pos, 1, 1)
        self.labels['profiles'].show_all()

    def back(self):
        if self.show_create is True:
            self.remove_create()
            return True
        return False

    def load_wcs(self):
        pass

    def process_update(self, action, data):
        if action != "notify_status_update":
            return
        #TODO: ADD WCS UPDATE

    def remove_create(self):
        if self.show_create is False:
            return

        self._screen.remove_keyboard()
        for child in self.content.get_children():
            self.content.remove(child)

        self.show_create = False
        self.content.add(self.labels['main_grid'])
        self.content.show()

    def remove_profile(self, profile):
        if profile not in self.profiles:
            return

        pos = self._get_position(profile)
        self.labels['profiles'].remove_row(pos)
        del self.profiles[profile]
        if not self.profiles:
            self._clear_profile()

    def _clear_profile(self):
        self.active_mesh = None
        self.update_graph()
        self.buttons['clear'].set_sensitive(False)

    def _get_position(self, profile):
        pl = list(self.profiles)
        if "default" in pl:
            pl.remove('default')
        profiles = sorted(pl)
        return profiles.index(profile) + 1 if profile != "default" else 0

    def tool_calibrate(self, widget):
        widget.set_sensitive(False)
        self._screen.show_popup_message(_("Calibrating"), level=1)
        if self._printer.get_stat("toolhead", "homed_axes") != "xyz":
            self._screen._ws.klippy.gcode_script("G28")
        module_homed_axes = self._printer.get_stat("module_5d", "toolhead").get("homed_axes", "")
        if module_homed_axes != "ac":
            self._screen._ws.klippy.gcode_script("HOME_MODULE A=1 C=1")
        self._screen._send_action(widget, "printer.gcode.script", {"script": "TOOL_CALIBRATE"})

    def send_clear_wcs(self, widget):
        self._screen._send_action(widget, "printer.gcode.script", {"script": "CLEAR_WCS"})

    def send_save_mesh(self, widget, profile):
        self._screen._send_action(widget, "printer.gcode.script", {"script": KlippyGcodes.bed_mesh_save(profile)})

    def send_remove_mesh(self, widget, profile):
        self._screen._send_action(widget, "printer.gcode.script", {"script": KlippyGcodes.bed_mesh_remove(profile)})
        self.remove_profile(profile)
