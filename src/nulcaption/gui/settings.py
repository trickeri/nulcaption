"""NulCaption settings window (PySide6).

Edits the shared config file (:mod:`nulcaption.config`) that ``nulcaption
caption`` reads as its defaults. Launched standalone (``nulcaption-settings``)
or from the Kdenlive "Caption Settings…" menu item — a separate process, so
changing settings never needs a Kdenlive rebuild.

PySide6 is an optional dependency (the ``gui`` extra); :func:`main` prints a
clear hint instead of a traceback if it isn't installed.
"""
from __future__ import annotations

import sys

from .. import config as cfgmod
from ..styles import PRESETS


def _seed_from_preset(cfg: cfgmod.CaptionConfig, preset_key: str) -> None:
    """Copy a built-in Style preset's appearance onto ``cfg`` in place."""
    st = PRESETS[preset_key]
    cfg.style_name = st.name
    cfg.fontname = st.fontname
    cfg.fontsize = st.fontsize
    cfg.highlight_rgb = st.highlight_rgb
    cfg.base_rgb = st.base_rgb
    cfg.bold = st.bold != 0
    cfg.italic = st.italic != 0
    cfg.outline_enabled = st.outline > 0
    cfg.outline_rgb = st.outline_rgb
    cfg.outline_thickness = st.outline or cfg.outline_thickness


def main(argv: list[str] | None = None) -> int:
    try:
        from PySide6 import QtGui, QtWidgets
    except ImportError:
        print(
            "error: the settings window needs PySide6.\n"
            "  install it into nulcaption's environment:\n"
            "    pipx inject nulcaption PySide6\n"
            "  (or `pip install 'nulcaption[gui]'` in a plain venv)",
            file=sys.stderr,
        )
        return 3

    cfg = cfgmod.load()

    class ColourButton(QtWidgets.QPushButton):
        """A swatch button that opens a colour picker and holds RRGGBB hex."""

        def __init__(self, rgb: str):
            super().__init__()
            self.setFixedWidth(90)
            self._rgb = ""
            self.set_rgb(rgb)
            self.clicked.connect(self._pick)

        def set_rgb(self, rgb: str) -> None:
            self._rgb = rgb.lstrip("#").upper()
            self.setText(f"#{self._rgb}")
            self.setStyleSheet(
                f"background:#{self._rgb}; color:#{_contrast(self._rgb)};"
            )

        def rgb(self) -> str:
            return self._rgb

        def _pick(self) -> None:
            c = QtWidgets.QColorDialog.getColor(QtGui.QColor(f"#{self._rgb}"), self)
            if c.isValid():
                self.set_rgb(f"{c.red():02X}{c.green():02X}{c.blue():02X}")

    class SettingsWindow(QtWidgets.QDialog):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("NulCaption Settings")
            form = QtWidgets.QFormLayout(self)

            # -- preset seeder --
            self.preset_seed = QtWidgets.QComboBox()
            self.preset_seed.addItems([k.capitalize() for k in sorted(PRESETS)])
            seed_btn = QtWidgets.QPushButton("Load")
            seed_btn.clicked.connect(self._seed)
            seed_row = QtWidgets.QHBoxLayout()
            seed_row.addWidget(self.preset_seed)
            seed_row.addWidget(seed_btn)
            form.addRow("Start from preset", _wrap(seed_row))

            form.addRow(_sep("Caption"))
            self.style_name = QtWidgets.QLineEdit(cfg.style_name)
            form.addRow("Style name", self.style_name)
            self.look = QtWidgets.QComboBox()
            self.look.addItems(["pop", "sweep"])
            self.look.setCurrentText(cfg.preset)
            form.addRow("Look", self.look)
            self.language = QtWidgets.QLineEdit(cfg.language)
            form.addRow("Language", self.language)
            self.max_words = _spin(1, 20, cfg.max_words)
            form.addRow("Max words / line", self.max_words)
            self.max_chars = _spin(10, 100, cfg.max_chars)
            form.addRow("Max chars / line", self.max_chars)

            form.addRow(_sep("Speech detection (VAD)"))
            self.vad = QtWidgets.QCheckBox("Enable VAD (keep captions off silence)")
            self.vad.setChecked(cfg.vad)
            form.addRow("", self.vad)
            self.vad_default = QtWidgets.QCheckBox("Use default threshold (0.5)")
            self.vad_thr = _dspin(0.0, 1.0, 0.05,
                                  cfg.vad_threshold if cfg.vad_threshold is not None else 0.5)
            self.vad_default.setChecked(cfg.vad_threshold is None)
            self.vad_default.toggled.connect(lambda on: self.vad_thr.setDisabled(on))
            self.vad_thr.setDisabled(cfg.vad_threshold is None)
            thr_row = QtWidgets.QHBoxLayout()
            thr_row.addWidget(self.vad_default)
            thr_row.addWidget(self.vad_thr)
            form.addRow("Threshold", _wrap(thr_row))

            form.addRow(_sep("Appearance"))
            self.fontname = QtWidgets.QFontComboBox()
            self.fontname.setCurrentFont(QtGui.QFont(cfg.fontname))
            form.addRow("Font", self.fontname)
            self.fontsize = _spin(8, 300, cfg.fontsize)
            form.addRow("Font size", self.fontsize)
            self.highlight = ColourButton(cfg.highlight_rgb)
            form.addRow("Highlight colour", self.highlight)
            self.base = ColourButton(cfg.base_rgb)
            form.addRow("Base colour", self.base)
            self.bold = QtWidgets.QCheckBox("Bold")
            self.bold.setChecked(cfg.bold)
            self.italic = QtWidgets.QCheckBox("Italic")
            self.italic.setChecked(cfg.italic)
            bi = QtWidgets.QHBoxLayout()
            bi.addWidget(self.bold)
            bi.addWidget(self.italic)
            bi.addStretch()
            form.addRow("", _wrap(bi))

            # outline
            self.outline_on = QtWidgets.QCheckBox("Outline")
            self.outline_on.setChecked(cfg.outline_enabled)
            self.outline_col = ColourButton(cfg.outline_rgb)
            self.outline_thk = _dspin(0.0, 20.0, 0.5, cfg.outline_thickness)
            o = QtWidgets.QHBoxLayout()
            o.addWidget(self.outline_on)
            o.addWidget(QtWidgets.QLabel("colour"))
            o.addWidget(self.outline_col)
            o.addWidget(QtWidgets.QLabel("thickness"))
            o.addWidget(self.outline_thk)
            o.addStretch()
            self.outline_on.toggled.connect(
                lambda on: (self.outline_col.setEnabled(on), self.outline_thk.setEnabled(on))
            )
            self.outline_col.setEnabled(cfg.outline_enabled)
            self.outline_thk.setEnabled(cfg.outline_enabled)
            form.addRow("", _wrap(o))

            # shadow
            self.shadow_on = QtWidgets.QCheckBox("Drop shadow")
            self.shadow_on.setChecked(cfg.shadow_enabled)
            self.shadow_col = ColourButton(cfg.shadow_rgb)
            self.shadow_x = _dspin(-50.0, 50.0, 0.5, cfg.shadow_x)
            self.shadow_y = _dspin(-50.0, 50.0, 0.5, cfg.shadow_y)
            s = QtWidgets.QHBoxLayout()
            s.addWidget(self.shadow_on)
            s.addWidget(QtWidgets.QLabel("colour"))
            s.addWidget(self.shadow_col)
            s.addWidget(QtWidgets.QLabel("X"))
            s.addWidget(self.shadow_x)
            s.addWidget(QtWidgets.QLabel("Y"))
            s.addWidget(self.shadow_y)
            s.addStretch()
            for w in (self.shadow_col, self.shadow_x, self.shadow_y):
                w.setEnabled(cfg.shadow_enabled)
            self.shadow_on.toggled.connect(
                lambda on: [w.setEnabled(on) for w in (self.shadow_col, self.shadow_x, self.shadow_y)]
            )
            form.addRow("", _wrap(s))

            sb = QtWidgets.QDialogButtonBox.StandardButton
            buttons = QtWidgets.QDialogButtonBox(sb.Save | sb.Cancel)
            buttons.accepted.connect(self._save)
            buttons.rejected.connect(self.reject)
            form.addRow(buttons)

        def _seed(self) -> None:
            key = self.preset_seed.currentText().lower()
            _seed_from_preset(cfg, key)
            self.style_name.setText(cfg.style_name)
            self.fontname.setCurrentFont(QtGui.QFont(cfg.fontname))
            self.fontsize.setValue(cfg.fontsize)
            self.highlight.set_rgb(cfg.highlight_rgb)
            self.base.set_rgb(cfg.base_rgb)
            self.bold.setChecked(cfg.bold)
            self.italic.setChecked(cfg.italic)
            self.outline_on.setChecked(cfg.outline_enabled)
            self.outline_col.set_rgb(cfg.outline_rgb)
            self.outline_thk.setValue(cfg.outline_thickness)

        def _save(self) -> None:
            new = cfgmod.CaptionConfig(
                preset=self.look.currentText(),
                language=self.language.text().strip() or "auto",
                vad=self.vad.isChecked(),
                vad_threshold=None if self.vad_default.isChecked() else round(self.vad_thr.value(), 3),
                max_words=self.max_words.value(),
                max_chars=self.max_chars.value(),
                style_name=self.style_name.text().strip() or "Nuldrums",
                fontname=self.fontname.currentFont().family(),
                fontsize=self.fontsize.value(),
                highlight_rgb=self.highlight.rgb(),
                base_rgb=self.base.rgb(),
                bold=self.bold.isChecked(),
                italic=self.italic.isChecked(),
                outline_enabled=self.outline_on.isChecked(),
                outline_rgb=self.outline_col.rgb(),
                outline_thickness=round(self.outline_thk.value(), 2),
                shadow_enabled=self.shadow_on.isChecked(),
                shadow_rgb=self.shadow_col.rgb(),
                shadow_x=round(self.shadow_x.value(), 2),
                shadow_y=round(self.shadow_y.value(), 2),
            )
            path = cfgmod.save(new)
            QtWidgets.QMessageBox.information(self, "Saved", f"Settings saved to\n{path}")
            self.accept()

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(argv or sys.argv)
    win = SettingsWindow()
    win.show()
    return app.exec()


# --- small Qt helpers (kept module-level so the window class stays readable) ---
def _spin(lo, hi, val):
    from PySide6 import QtWidgets
    s = QtWidgets.QSpinBox()
    s.setRange(lo, hi)
    s.setValue(int(val))
    return s


def _dspin(lo, hi, step, val):
    from PySide6 import QtWidgets
    s = QtWidgets.QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setSingleStep(step)
    s.setValue(float(val))
    return s


def _wrap(layout):
    from PySide6 import QtWidgets
    w = QtWidgets.QWidget()
    w.setLayout(layout)
    return w


def _sep(text):
    from PySide6 import QtWidgets
    lbl = QtWidgets.QLabel(f"<b>{text}</b>")
    return lbl


def _contrast(rgb: str) -> str:
    """Black or white text for legibility on the given RRGGBB swatch."""
    try:
        r, g, b = int(rgb[0:2], 16), int(rgb[2:4], 16), int(rgb[4:6], 16)
    except ValueError:
        return "000000"
    return "000000" if (0.299 * r + 0.587 * g + 0.114 * b) > 140 else "FFFFFF"


if __name__ == "__main__":
    raise SystemExit(main())
