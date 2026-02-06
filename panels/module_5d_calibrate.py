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
        self.distance = ".05"
        section = self._printer.get_config_section("bed_mesh")
        self.mesh_radius = section['mesh_radius'] if 'mesh_radius' in section else None
        self.profiles = {}
        self.buttons = {
            'calib': self._gtk.Button("refresh", _("Calibrate"), "color3", self.bts, Gtk.PositionType.LEFT, 1),
            'clear': self._gtk.Button("cancel", _("Clear"), "color2", self.bts, Gtk.PositionType.LEFT, 1),
            'a_plus': self._gtk.Button("increase", "", "color2", self.bts, Gtk.PositionType.LEFT, 1),
            'a_minus': self._gtk.Button("decrease", "", "color2", self.bts, Gtk.PositionType.LEFT, 1),
            'wcs1x+': self._gtk.Button("increase", "", "color2", self.bts, Gtk.PositionType.LEFT, 1),
            'wcs1x-': self._gtk.Button("decrease", "", "color2", self.bts, Gtk.PositionType.LEFT, 1),
            'wcs1y+': self._gtk.Button("increase", "", "color2", self.bts, Gtk.PositionType.LEFT, 1),
            'wcs1y-': self._gtk.Button("decrease", "", "color2", self.bts, Gtk.PositionType.LEFT, 1),
            'wcs1z+': self._gtk.Button("increase", "", "color2", self.bts, Gtk.PositionType.LEFT, 1),
            'wcs1z-': self._gtk.Button("decrease", "", "color2", self.bts, Gtk.PositionType.LEFT, 1),
            'wcs2x+': self._gtk.Button("increase", "", "color2", self.bts, Gtk.PositionType.LEFT, 1),
            'wcs2x-': self._gtk.Button("decrease", "", "color2", self.bts, Gtk.PositionType.LEFT, 1),
            'wcs2y+': self._gtk.Button("increase", "", "color2", self.bts, Gtk.PositionType.LEFT, 1),
            'wcs2y-': self._gtk.Button("decrease", "", "color2", self.bts, Gtk.PositionType.LEFT, 1),
            'wcs2z+': self._gtk.Button("increase", "", "color2", self.bts, Gtk.PositionType.LEFT, 1),
            'wcs2z-': self._gtk.Button("decrease", "", "color2", self.bts, Gtk.PositionType.LEFT, 1),
        }
        self.buttons['clear'].connect("clicked", self.send_clear_wcs)
        self.buttons['calib'].connect("clicked", self.show_tool_calibrate)
        self.buttons['a_plus'].connect("clicked", self.adjust_a, "+")
        self.buttons['a_minus'].connect("clicked", self.adjust_a, "-")
        for wcs in range(1, 3):
            for axis in 'xyz':
                self.buttons[f'wcs{wcs}{axis}+'].connect('clicked', self.adjust_wcs, wcs, axis.capitalize(), "+")
                self.buttons[f'wcs{wcs}{axis}-'].connect('clicked', self.adjust_wcs, wcs, axis.capitalize(), "-")

        topbar = Gtk.Box(spacing=5, hexpand=True, vexpand=False)

        topbar.add(self.buttons['clear'])
        topbar.add(self.buttons['calib'])



        grid = Gtk.Grid(column_homogeneous=True)
        grid.attach(topbar, 0, 0, 2, 1)
        scale_f = 0.6 if self._screen.vertical_mode else 0.8
        self.labels['graph'] = self._gtk.Image("wcs-graph", self._gtk.content_width * scale_f, self._gtk.content_height * scale_f)

        self.labels['adjust_grid'] = Gtk.Grid(column_homogeneous=True)
        self.labels['adjust_grid'].attach(self.buttons['a_minus'], 0, 0, 1, 1)
        self.labels['a_offset'] = Gtk.Label()
        self.labels['adjust_grid'].attach(self.labels['a_offset'], 1, 0, 1, 1)
        self.labels['adjust_grid'].attach(self.buttons['a_plus'], 2, 0, 1, 1)
        for wcs in range(1, 3):
            self.labels[f'wcs{wcs}'] = Gtk.Label(f'WCS{wcs}')
            self.labels['adjust_grid'].attach(self.labels[f'wcs{wcs}'], 0, wcs + 4 * (wcs - 1), 3, 1)
            for axis_idx, axis in enumerate('xyz'):
                self.labels[f'wcs{wcs}{axis}'] = Gtk.Label()
                self.labels['adjust_grid'].attach(self.buttons[f"wcs{wcs}{axis}-"], 0, wcs + 1 + axis_idx + 4 * (wcs - 1), 1, 1)
                self.labels['adjust_grid'].attach(self.labels[f'wcs{wcs}{axis}'], 1, wcs + 1 + axis_idx + 4 * (wcs - 1), 1, 1)
                self.labels['adjust_grid'].attach(self.buttons[f"wcs{wcs}{axis}+"], 2, wcs + 1 + axis_idx + 4 * (wcs - 1), 1, 1)

        if self._screen.vertical_mode:
            grid.attach(self.labels['graph'], 0, 2, 2, 1)
            grid.attach(self.labels['adjust_grid'], 0, 3, 2, 1)
        else:
            grid.attach(self.labels['graph'], 0, 2, 1, 1)
            grid.attach(self.labels['adjust_grid'], 1, 2, 1, 1)

        self.labels['main_grid'] = grid
        self.content.add(self.labels['main_grid'])

        self.load_wcs()

    def activate(self):
        self.load_wcs()

    def add_profile(self, profile):
        logging.debug(f"Adding Profile: {profile}")
        name = self._gtk.Button(label=f"<big><b>{profile}</b></big>")
        name.get_children()[0].set_use_markup(True)
        name.get_children()[0].set_line_wrap(True)
        name.get_children()[0].set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        name.set_vexpand(False)
        name.set_halign(Gtk.Align.START)

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
        wcs_offsets = self._printer.get_stat("module_5d", "wcs_offsets")
        if not wcs_offsets:
            return
        for wcs in range(1, 3):
            for axis_idx, axis in enumerate('xyz'):
                self.labels[f'wcs{wcs}{axis}'].set_text(f"{axis.capitalize()}: {wcs_offsets[wcs][axis_idx]:.2f}")


    def process_update(self, action, data):
        if action != "notify_status_update":
            return
        if "module_5d" in data:
            if 'homing_origin' in data['module_5d']:
                self.labels['a_offset'].set_text(
                    f"A: {data['module_5d']['homing_origin'][0]:.2f}"
                )
            if "wcs_offsets" in data["module_5d"]:
                for wcs in range(1, 3):
                    for axis_idx, axis in enumerate('xyz'):
                        self.labels[f'wcs{wcs}{axis}'].set_text(f"{axis.capitalize()}: {data['module_5d']['wcs_offsets'][wcs][axis_idx]:.2f}")

    def remove_create(self):
        if self.show_create is False:
            return

        self._screen.remove_keyboard()
        for child in self.content.get_children():
            self.content.remove(child)

        self.show_create = False
        self.content.add(self.labels['main_grid'])
        self.content.show()


    def _get_position(self, profile):
        pl = list(self.profiles)
        if "default" in pl:
            pl.remove('default')
        profiles = sorted(pl)
        return profiles.index(profile) + 1 if profile != "default" else 0

    def tool_calibrate(self, widget):
        widget.set_sensitive(False)
        tool_radius = self.labels['tool_radius'].get_text()
        self._screen.show_popup_message(_("Calibrating"), level=1)
        if self._printer.get_stat("toolhead", "homed_axes") != "xyz":
            self._screen._ws.klippy.gcode_script("G28")
        module_homed_axes = self._printer.get_stat("module_5d", "toolhead").get("homed_axes", "")
        if module_homed_axes != "ac":
            self._screen._ws.klippy.gcode_script("HOME_MODULE A=1 C=1")
        self._screen._send_action(widget, "printer.gcode.script", {"script": f"TOOL_CALIBRATE TOOL_RADIUS={tool_radius}"})

    def adjust_a(self, widget, direction):
        script = f"SET_GCODE_OFFSET A_ADJUST={direction}{self.distance}"
        self._screen._send_action(widget, "printer.gcode.script", {"script": script})

    def adjust_wcs(self, widget, wcs, axis, direction):
        logging.info(f'adjust WCS: {wcs}, {axis}, {direction}')
        dist = f"{direction}{self.distance}"
        script = f"G10 L2 R1 P{wcs + 1} {axis}{dist}"
        self._screen._send_action(widget, "printer.gcode.script", {"script": script})

    def show_tool_calibrate(self, widget):

        for child in self.content.get_children():
            self.content.remove(child)

        if "tool_calibrate" not in self.labels:
            pl = Gtk.Label(label=_("Profile Name:"), hexpand=False)
            self.labels['tool_radius'] = Gtk.Entry(hexpand=True, text='3.0')
            self.labels['tool_radius'].connect("activate", self.tool_calibrate)
            self.labels['tool_radius'].connect("touch-event", self._screen.show_keyboard)
            self.labels['tool_radius'].connect("button-press-event", self._screen.show_keyboard)

            save = self._gtk.Button("complete", _("Save"), "color3")
            save.set_hexpand(False)
            save.connect("clicked", self.tool_calibrate)

            box = Gtk.Box()
            box.pack_start(self.labels['tool_radius'], True, True, 5)
            box.pack_start(save, False, False, 5)

            self.labels['tool_calibrate'] = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5,
                                                    valign=Gtk.Align.CENTER, hexpand=True, vexpand=True)
            self.labels['tool_calibrate'].pack_start(pl, True, True, 5)
            self.labels['tool_calibrate'].pack_start(box, True, True, 5)

        self.content.add(self.labels['tool_calibrate'])
        self.labels['tool_radius'].grab_focus_without_selecting()
        self.show_create = True

    def send_clear_wcs(self, widget):
        self._screen._send_action(widget, "printer.gcode.script", {"script": "CLEAR_WCS"})
