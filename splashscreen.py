import tkinter as tk
from PIL import Image, ImageTk

# splash screen, creates window and displays image of photon logo for 3 seconds before deleting image.
# currently set up in a way that keeps the window, can be altered to destroy window aswell.

class SplashScreen:
    def __init__(self, on_close=None, image_path="logo.jpg", duration_ms=3000):
        # window setup
        self.root = tk.Tk()
        self.root.title("Splash Screen")
        self.on_close = on_close

        width, height = 800, 600 # subject to change

        # center the window
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        img = Image.open(image_path).resize((width, height), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(img)

        # create and display img, saved to self for finish to clear it later
        self._label = tk.Label(self.root, image=self._photo, bg="black", padx=0, pady=0)
        self._label.pack()
        
        # after splashscreen runs duration, call finish
        self.root.after(duration_ms, self._finish)
        
    # destroy splash screen, on close is when we add stuff after, so when splash screen closes it moves on. 
    def _finish(self):
        # if you want to destroy window as well, uncomment line below
        self.root.destroy()
        # self._label.config(image="")
        if self.on_close:
            self.on_close()

    def show(self):
        self.root.mainloop()

# for testing
if __name__ == "__main__":
    SplashScreen().show()