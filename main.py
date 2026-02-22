# main.py
import tkinter as tk
from src.ui.app_ui import LocalDropUI

def main():
    root = tk.Tk()
    app = LocalDropUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
