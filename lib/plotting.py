# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2026, Đỗ Lê Chí Kiên and Nguyễn Trương Đăng Quang
# Main libraries: Matplotlib; Python stdlib (os).
"""Choose an interactive Matplotlib backend when a window is requested.

Matplotlib falls back to `Agg` without saying so when no GUI toolkit can be
loaded, and `plt.show()` then does nothing. Call `use_interactive` before
importing `pyplot`; if it returns None, say why instead of rendering silence.
"""
import os

NON_GUI = ('agg', 'pdf', 'svg', 'ps', 'cairo', 'template')


def use_interactive():
    """Return an interactive backend name, or None when none can be loaded."""
    import matplotlib
    if matplotlib.get_backend().lower() not in NON_GUI:
        return matplotlib.get_backend()
    if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        return None
    for candidate in ('QtAgg', 'TkAgg', 'Qt5Agg', 'GTK3Agg'):
        try:
            matplotlib.use(candidate, force=True)
            chosen = matplotlib.get_backend()
            if chosen.lower() not in NON_GUI:
                return chosen
        except Exception:
            continue
    try:
        matplotlib.use('Agg', force=True)
    except Exception:
        pass
    return None


def unavailable_message():
    return ('không mở được cửa sổ đồ hoạ: cần PyQt6 hoặc python3-tk, kèm thư viện '
            'hệ thống (sudo apt install libzstd1 libxkbcommon0 libgl1). '
            'Bỏ cờ yêu cầu cửa sổ để ghi PNG.')
