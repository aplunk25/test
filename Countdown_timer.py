import tkinter as tk
import music_player

from PIL import Image, ImageTk
import UDP_Client


# Countdown timer class, will be open for 30 seconds, showing each second as an image, then broadcasts codes


class CountdownTimer:

    def __init__(self, parent, on_close=None, image_path="countdown_images", seconds=30):

        # Create the main window

        self.root = tk.Toplevel(parent)

        self.root.title("Countdown Timer")

        self.on_close = on_close

        self.image_path = image_path

        self.seconds = seconds

        self.width, self.height = 800, 600
        
        self.timer_width, self.timer_height = 100, 100
        
        self.timer_x = (self.width // 2)
        
        self.timer_y = (self.height // 2) + 50

        self.start_code = 202

        # center the window

        screen_w = self.root.winfo_screenwidth()

        screen_h = self.root.winfo_screenheight()

        x = (screen_w - self.width) // 2

        y = (screen_h - self.height) // 2

        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")

        # Canvas for layering images
        self.canvas = tk.Canvas(
            self.root, width=self.width, height=self.height)
        self.canvas.pack()

        # Load background image
        bg_img = Image.open(f"{self.image_path}/background.tif")
        bg_img = bg_img.resize((self.width, self.height), Image.LANCZOS)
        self.bg_photo = ImageTk.PhotoImage(bg_img)

        # Draw background
        self.canvas.create_image(0, 0, anchor="nw", image=self.bg_photo)

        # Placeholder for countdown image
        self.countdown_item = self.canvas.create_image(
            self.timer_x, self.timer_y, anchor="center"
        )

        # Start the countdown
        self.root.after(17000, music_player.play_music) # 17 sec delay, music start
        self.start_countdown()

    def start_countdown(self):

        # If timer gets to zero, finish
        if self.seconds <= 0:
            UDP_Client.send_packet(self.start_code)
            self._finish()
            return

        try:
            # Load the image for the current second
            img = Image.open(f"{self.image_path}/{self.seconds}.tif")
            img = img.resize((self.timer_width, self.timer_height), Image.LANCZOS)
            self.count_photo = ImageTk.PhotoImage(
                img)  # Prevents garbage collection
            self.canvas.itemconfig(self.countdown_item, image=self.count_photo)

        except Exception as e:
            print(f"Error loading the image for second {self.seconds}: {e}")

        self.seconds -= 1

        # Call again after 1 second (1000 ms)
        self.root.after(1000, self.start_countdown)

    # destroy splash screen, on close is when we add stuff after, so when splash screen closes it moves on.

    def _finish(self):


        # self._label.config(image="")

        if self.on_close:

            self.on_close()
        
        self.root.destroy()

    def show(self):

        self.root.mainloop()


# for testing
if __name__ == "__main__":

    CountdownTimer(seconds=30).show()
