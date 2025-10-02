# main.py
import ttkbootstrap as tb
from login import show_login

if __name__ == "__main__":
    # 1) Create your window with the flatly theme
    root = tb.Window(themename="flatly")

    # 2) Grab the Style instance and override the built-in 'primary' (and any other)
    style = root.style
    style.colors.set('primary', '#d9534f')   # your brand-red
    style.colors.set('danger',  '#c9302c')   # a slightly darker red for hovers, borders, etc.

    # 3) Now register your custom widget styles
    style.configure(
        'Sidebar.TFrame',
        background='#d9534f',
        borderwidth=0
    )
    style.configure(
        'Sidebar.TButton',
        background='#d9534f',
        foreground='white',
        font=('Segoe UI', 11, 'bold'),
    )
    style.map(
        'Sidebar.TButton',
        background=[('active', '#c9302c')]
    )

    style.configure(
        'RouterCard.TLabelframe',
        background='white',
        bordercolor='#d9534f',
        borderwidth=1,
        relief='flat'
    )
    style.configure(
        'RouterCard.TLabelframe.Label',
        background='white',
        foreground='#d9534f',
        font=('Segoe UI', 10, 'bold')
    )
    style.map(
        'RouterCard.TLabelframe',
        bordercolor=[('active', '#c9302c')]
    )

    # 4) Fire off your login (and then dashboard) as usual
    show_login(root)
    root.mainloop()
