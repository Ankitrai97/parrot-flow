"""Per-pixel-alpha Windows HUD; no browser surface or native frame at the edge."""
import ctypes
import math
import time
from ctypes import wintypes


class Blend(ctypes.Structure):
    _fields_ = [('operation', ctypes.c_ubyte), ('flags', ctypes.c_ubyte),
                ('alpha', ctypes.c_ubyte), ('format', ctypes.c_ubyte)]


def pill_size(state, expanded=False):
    if state == 'idle':
        return (66 if expanded else 36), 14
    return (102, 28) if state == 'recording' else (180 if state == 'pending' else 144, 24)


def compact_message(state, message):
    lowered = message.lower()
    if any(word in lowered for word in ('no voice', 'no audible', 'no audio', 'no speech', 'silence')):
        return 'No voice input'
    if state == 'pending':
        return 'Text saved'
    if state == 'processing':
        return 'Preparing…' if 'prepar' in lowered else 'Transcribing…'
    return 'Check settings' if state == 'error' else 'See settings'


class NativePill:
    def __init__(self, owner):
        import clr
        clr.AddReference('System.Drawing')
        clr.AddReference('System.Windows.Forms')
        import System.Drawing as D
        import System.Windows.Forms as F
        self.D, self.F, self.owner = D, F, owner
        self.form = F.Form()
        self.form.Text = 'Parrot Flow'
        self.form.FormBorderStyle = getattr(F.FormBorderStyle, 'None')
        self.form.ShowInTaskbar = False
        self.form.TopMost = True
        self.form.StartPosition = F.FormStartPosition.Manual
        self.form.AutoScaleMode = getattr(F.AutoScaleMode, 'None')
        self.state, self.message, self.expanded = 'idle', '', False
        self.level, self.receiving, self.phase = 0, False, 0
        self.hits = []
        self._rendering = False
        self.down = None
        self._notice_deadline = None
        self.form.MouseEnter += self.enter
        self.form.MouseLeave += self.leave
        self.form.MouseDown += self.mouse_down
        self.form.MouseUp += self.mouse_up
        self.form.FormClosing += self.closing
        self.form.HandleCreated += self.restyle
        self.timer = F.Timer()
        self.timer.Interval = 100
        self.timer.Tick += self.tick
        self.timer.Start()
        self.user, self.gdi = ctypes.windll.user32, ctypes.windll.gdi32
        self.user.GetDC.argtypes, self.user.GetDC.restype = (wintypes.HWND,), wintypes.HDC
        self.user.ReleaseDC.argtypes = (wintypes.HWND, wintypes.HDC)
        self.gdi.CreateCompatibleDC.argtypes, self.gdi.CreateCompatibleDC.restype = (wintypes.HDC,), wintypes.HDC
        self.gdi.SelectObject.argtypes, self.gdi.SelectObject.restype = (wintypes.HDC, wintypes.HANDLE), wintypes.HANDLE
        self.gdi.DeleteObject.argtypes = (wintypes.HANDLE,)
        self.gdi.DeleteDC.argtypes = (wintypes.HDC,)
        self.user.UpdateLayeredWindow.argtypes = (wintypes.HWND, wintypes.HDC,
            ctypes.POINTER(wintypes.POINT), ctypes.POINTER(wintypes.SIZE), wintypes.HDC,
            ctypes.POINTER(wintypes.POINT), wintypes.DWORD, ctypes.POINTER(Blend), wintypes.DWORD)
        self.handle = wintypes.HWND(self.form.Handle.ToInt64())
        from .hud import _get_style, _set_style
        _set_style(self.handle, -20, _get_style(self.handle, -20) | 0x80000 | 0x08000000 | 0x80)
        self.tooltip = F.ToolTip()

    def restyle(self, *_):
        from .hud import _get_style, _set_style
        self.handle = wintypes.HWND(self.form.Handle.ToInt64())
        _set_style(self.handle, -20, _get_style(self.handle, -20) | 0x80000 | 0x08000000)

    def closing(self, sender, event):
        event.Cancel = not self.owner._closed.is_set()

    def enter(self, *_):
        if self.state == 'idle':
            self.expanded = True
            self.render()

    def leave(self, *_):
        # Use the actual bounds after expansion; transient leave events during
        # resize must not collapse the pill underneath the pointer.
        if not self._rendering and self.expanded and not self.form.Bounds.Contains(self.F.Cursor.Position):
            self.expanded = False
            self.render()

    def mouse_down(self, sender, event):
        if event.Button == self.F.MouseButtons.Left:
            self.down = (event.X, event.Y)

    def mouse_up(self, sender, event):
        down, self.down = self.down, None
        if down is None or self.state == 'processing' or self.owner._is_busy():
            return
        if math.hypot(event.X-down[0], event.Y-down[1]) > 4:
            return
        for rectangle, action in self.hits:
            if rectangle.Contains(event.X, event.Y) and rectangle.Contains(*down):
                action()
                break

    def tick(self, *_):
        self._expire_notice()
        if self.form.Visible:
            self.phase += .18
            if self.state == 'recording' and self.owner._meter:
                self.level, self.receiving = self.owner._meter()
                self.level = min(1, max(0, self.level * 20)) if self.receiving else 0
            self.leave()
            self.render()

    def _expire_notice(self):
        deadline = self._notice_deadline
        if deadline is None or time.monotonic() < deadline:
            return
        self._notice_deadline = None
        if (self.state in ('error', 'notice')
                and self.owner._state == self.state and self.owner._message == self.message
                and not self.owner._is_busy()):
            self.owner.show_idle()

    def show(self, state, message):
        self.state, self.message = state, message
        self._notice_deadline = (time.monotonic() + 7
            if state in ('error', 'notice') and compact_message(state, message) == 'No voice input'
            else None)
        if state != 'idle':
            self.expanded = False
        self.form.Show()
        self.render()
        self.user.ShowWindow(self.handle, 4)

    def hide(self):
        self.form.Hide()

    def close(self):
        self.timer.Stop()
        self.timer.Dispose()
        self.tooltip.Dispose()
        self.form.Dispose()

    def render(self):
        if self._rendering:
            return
        self._rendering = True
        D = self.D
        # WinForms can recreate HWNDs on Show/ownership changes. Never paint
        # into the stale handle; apply layered styles to the current one.
        from .hud import _get_style, _set_style
        self.handle = wintypes.HWND(self.form.Handle.ToInt64())
        _set_style(self.handle, -20, _get_style(self.handle, -20) | 0x80000 | 0x08000000)
        scale = self.form.DeviceDpi / 96
        width, height = pill_size(self.state, self.expanded)
        # Two transparent pixels allow anti-aliased edges to blend with desktop.
        w, h = math.ceil((width+4)*scale), math.ceil((height+4)*scale)
        work = self.F.Screen.PrimaryScreen.WorkingArea
        anchor_width = math.ceil(40*scale) if self.state == 'idle' else w
        x, y = work.Left+(work.Width-anchor_width)//2, work.Bottom-h-round(10*scale)
        self.form.Bounds = D.Rectangle(x, y, w, h)
        bitmap = D.Bitmap(w, h, D.Imaging.PixelFormat.Format32bppArgb)
        graphics = D.Graphics.FromImage(bitmap)
        resources = []
        def brush(color):
            value = D.SolidBrush(D.ColorTranslator.FromHtml(color))
            resources.append(value)
            return value
        def pen(color, thickness):
            value = D.Pen(D.ColorTranslator.FromHtml(color), thickness)
            value.StartCap = value.EndCap = D.Drawing2D.LineCap.Round
            resources.append(value)
            return value
        def hit(left, right, callback):
            self.hits.append((D.Rectangle(round((left+2)*scale), round(2*scale),
                                          round((right-left)*scale), round(height*scale)), callback))
        try:
            graphics.Clear(D.Color.Transparent)
            graphics.SmoothingMode = D.Drawing2D.SmoothingMode.AntiAlias
            graphics.ScaleTransform(scale, scale)
            graphics.TranslateTransform(2., 2.)
            path = D.Drawing2D.GraphicsPath()
            resources.append(path)
            path.AddArc(0., 0., float(height), float(height), 90., 180.)
            path.AddArc(float(width-height), 0., float(height), float(height), 270., 180.)
            path.CloseFigure()
            graphics.FillPath(brush('#101010'), path)
            self.hits = []
            if self.state == 'idle':
                glow = int(155 + 80*(.5+.5*math.sin(self.phase)))
                green = D.SolidBrush(D.Color.FromArgb(255, 54, glow, 120))
                resources.append(green)
                graphics.FillEllipse(green, 9., 4.5, 5., 5.)
                graphics.FillEllipse(brush('#dddddd'), 23., 5., 4., 4.)
                hit(18, 33, self.owner.toggle)
                if self.expanded:
                    self.draw_gear(graphics, pen('#dddddd', 1.2), 50., 7.)
                    hit(38, 64, self.owner.open_settings)
                self.tooltip.SetToolTip(self.form, 'White dot: start dictation · Hover for settings')
            elif self.state == 'recording':
                graphics.FillEllipse(brush('#343434'), 5., 4., 20., 20.)
                graphics.DrawLine(pen('#eeeeee', 1.5), 12., 11., 18., 17.)
                graphics.DrawLine(pen('#eeeeee', 1.5), 18., 11., 12., 17.)
                graphics.FillEllipse(brush('#f5f5f5'), float(width-25), 4., 20., 20.)
                check = pen('#171717', 1.7)
                graphics.DrawLine(check, float(width-19), 14., float(width-16), 17.)
                graphics.DrawLine(check, float(width-16), 17., float(width-11), 11.)
                wave = pen('#eeeeee', 1.8)
                for i in range(12):
                    bar = 2 + 15*self.level*math.sin(math.pi*(i+.5)/12)**1.5
                    bx = 32 + i*3.4
                    graphics.DrawLine(wave, bx, 14-bar/2, bx, 14+bar/2)
                hit(2, 28, self.owner.cancel)
                hit(width-28, width-2, self.owner.stop)
                self.tooltip.SetToolTip(self.form, 'Listening · Cancel on left · Finish on right')
            else:
                graphics.FillEllipse(brush('#d8bb70'), 10., 11., 6., 6.)
                font = D.Font('Segoe UI', 8.)
                resources.append(font)
                fmt = D.StringFormat()
                resources.append(fmt)
                fmt.LineAlignment = D.StringAlignment.Center
                fmt.Trimming = D.StringTrimming.EllipsisCharacter
                fmt.FormatFlags = D.StringFormatFlags.NoWrap
                right = 85 if self.state == 'pending' else 26
                graphics.DrawString(compact_message(self.state, self.message), font, brush('#dddddd'),
                    D.RectangleF(23., 0., float(width-right-23), float(height)), fmt)
                if self.state != 'processing':
                    self.draw_gear(graphics, pen('#dddddd', 1.3), float(width-16), 14.)
                    hit(width-30, width, self.owner.open_settings)
                if self.state == 'pending':
                    graphics.DrawString('Insert', font, brush('#dddddd'), float(width-78), 6.)
                    hit(width-82, width-32, self.owner.insert)
                self.tooltip.SetToolTip(self.form, self.message)
            if getattr(self.owner, '_render_dump', None):
                bitmap.Save(self.owner._render_dump, D.Imaging.ImageFormat.Png)
            dc = self.user.GetDC(None)
            memory = self.gdi.CreateCompatibleDC(dc)
            handle = bitmap.GetHbitmap(D.Color.FromArgb(0)).ToInt64()
            previous = self.gdi.SelectObject(memory, handle)
            try:
                ok = self.user.UpdateLayeredWindow(self.handle, dc,
                    ctypes.byref(wintypes.POINT(x,y)), ctypes.byref(wintypes.SIZE(w,h)), memory,
                    ctypes.byref(wintypes.POINT(0,0)), 0, ctypes.byref(Blend(0,0,255,1)), 2)
                if not ok:
                    raise ctypes.WinError()
            finally:
                self.gdi.SelectObject(memory, previous)
                self.gdi.DeleteObject(handle)
                self.gdi.DeleteDC(memory)
                self.user.ReleaseDC(None, dc)
        finally:
            for resource in resources:
                resource.Dispose()
            graphics.Dispose()
            bitmap.Dispose()
            self._rendering = False

    @staticmethod
    def draw_gear(graphics, pen, x, y):
        graphics.DrawEllipse(pen, x-3.5, y-3.5, 7., 7.)
        graphics.DrawEllipse(pen, x-1., y-1., 2., 2.)
        for i in range(8):
            angle = math.pi*i/4
            graphics.DrawLine(pen, x+3.5*math.cos(angle), y+3.5*math.sin(angle),
                              x+5*math.cos(angle), y+5*math.sin(angle))
