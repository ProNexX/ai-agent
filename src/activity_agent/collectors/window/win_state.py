import win32con
import win32gui

def get_foreground_windows():
    active_windows = []

    def callback(h, _):
        if is_real_app(h):
            title = win32gui.GetWindowText(h)
            active_windows.append(title)

    win32gui.EnumWindows(callback, None)

    return active_windows

def is_real_app(h):
    if not win32gui.IsWindowVisible(h):
        return False

    title = win32gui.GetWindowText(h)
    if not title:
        return False

    if win32gui.GetParent(h) != 0:
        return False

    ex_style = win32gui.GetWindowLong(h, win32con.GWL_EXSTYLE)
    if ex_style & win32con.WS_EX_TOOLWINDOW:
        return False

    return True

print(get_foreground_windows())