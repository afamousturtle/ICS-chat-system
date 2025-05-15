#!/usr/bin/env python3
# -*- coding: utf-8 -*-


# import all the required  modules
import threading
import select
from tkinter import *
from tkinter import font
from tkinter import ttk
from chat_utils import *
import json
from PIL import Image, ImageGrab, ImageOps, ImageTk, ImageSequence
import numpy as np
from tkinter import messagebox

# GUI class for the chat
class GUI:
    # constructor method
    def __init__(self, send, recv, sm, s):
        # chat window which is currently hidden
        self.writing_window = Tk()
        self.writing_window.withdraw()
        self.send = send
        self.recv = recv
        self.sm = sm
        self.socket = s
        self.my_msg = ""
        self.system_msg = ""
        self.socket_lock = threading.Lock()
    
    def login(self):
        self.login = Toplevel()
        self.login.title("Login / Register")
        self.login.resizable(width=False, height=False)
        self.login.configure(width=400, height=350)

        self.pls = Label(self.login, text="Login or Register to Continue",
                        justify=CENTER, font="Helvetica 14 bold")
        self.pls.place(relheight=0.15, relx=0.2, rely=0.07)

        self.labelName = Label(self.login, text="Username:", font="Helvetica 12")
        self.labelName.place(relheight=0.1, relx=0.1, rely=0.25)
        self.entryName = Entry(self.login, font="Helvetica 14")
        self.entryName.place(relwidth=0.5, relheight=0.1, relx=0.35, rely=0.25)

        self.labelPwd = Label(self.login, text="Password:", font="Helvetica 12")
        self.labelPwd.place(relheight=0.1, relx=0.1, rely=0.4)
        self.entryPwd = Entry(self.login, font="Helvetica 14", show="*")
        self.entryPwd.place(relwidth=0.5, relheight=0.1, relx=0.35, rely=0.4)

        self.entryName.focus()

        self.go_login = Button(self.login, text="Login", font="Helvetica 12 bold",
                            command=lambda: self.goAhead("login"))
        self.go_login.place(relx=0.2, rely=0.65, relwidth=0.25, relheight=0.15)

        self.go_register = Button(self.login, text="Register", font="Helvetica 12 bold",
                                command=lambda: self.goAhead("register"))
        self.go_register.place(relx=0.55, rely=0.65, relwidth=0.25, relheight=0.15)
        self.writing_window.mainloop()
  
    def goAhead(self, action):
        name = self.entryName.get().strip()
        password = self.entryPwd.get().strip()

        if not name or not password:
            messagebox.showwarning("Input Error", "Please enter both username and password.")
            return

        msg = json.dumps({"action": action, "name": name, "password": password})
        self.send(msg)
        response = json.loads(self.recv())

        if response["status"] == "ok":
            if action == "register":
                
                login_msg = json.dumps({"action": "login", "name": name, "password": password})
                self.send(login_msg)
                login_resp = json.loads(self.recv())

                if login_resp["status"] == "ok":
                    self._login_success(name)
                else:
                    messagebox.showerror("Auto Login Failed", "Registration succeeded, but auto login failed. Please try logging in manually.")
            else:
                self._login_success(name)

        elif response["status"] == "duplicate":
            messagebox.showerror("Error", "This user is already logged in elsewhere.")
        else:
            if action == "login":
                messagebox.showerror("Login Failed", "Invalid username or password.")
            else:
                messagebox.showerror("Registration Failed", "Username already exists.")

    def _login_success(self, name):
        
        self.login.destroy()
        self.sm.set_state(S_LOGGEDIN)
        self.sm.set_myname(name)
        self.layout(name)
        self.textCons.config(state=NORMAL)
        self.textCons.insert(END, menu + "\n\n")
        self.textCons.config(state=DISABLED)
        self.textCons.see(END)
        process = threading.Thread(target=self.proc)
        process.daemon = True
        process.start()

    # The main layout of the chat
    def layout(self,name):
        self.name = name
        # to show chat window
        self.writing_window.deiconify()
        self.writing_window.title("CHATROOM")
        self.writing_window.resizable(width = False,
                              height = False)
        self.writing_window.configure(width = 470,
                              height = 550,
                              bg = "#17202A")
        self.labelHead = Label(self.writing_window,
                             bg = "#17202A", 
                              fg = "#EAECEE",
                              text = self.name ,
                               font = "Helvetica 13 bold",
                               pady = 5)
          
        self.labelHead.place(relwidth = 1)
        self.line = Label(self.writing_window,
                          width = 450,
                          bg = "#ABB2B9")
          
        self.line.place(relwidth = 1,
                        rely = 0.07,
                        relheight = 0.012)
          
        self.textCons = Text(self.writing_window,
                             width = 20, 
                             height = 80,
                             bg = "#17202A",
                             fg = "#EAECEE",
                             font = "Helvetica 14", 
                             padx = 5,
                             pady = 5)
          
        self.textCons.place(relheight = 0.745,
                            relwidth = 1, 
                            rely = 0.08)
          
        self.labelBottom = Label(self.writing_window,
                                 bg = "#ABB2B9",
                                 height = 80)
          
        self.labelBottom.place(relwidth = 1,
                               rely = 0.825)
          
        self.entryMsg = Entry(self.labelBottom,
                              bg = "#2C3E50",
                              fg = "#EAECEE",
                              font = "Helvetica 13")
          
        # place the given widget
        # into the gui window
        self.entryMsg.place(relwidth = 0.5,
                            relheight = 0.06,
                            rely = 0.008,
                            relx = 0.011)
          
        self.entryMsg.focus()
          
        # create a Send Button
        self.buttonMsg = Button(self.labelBottom,
                                text = "Send",
                                font = "Helvetica 10 bold", 
                                width = 20,
                                bg = "#ABB2B9",
                                command = lambda : self.sendButton(self.entryMsg.get()))
          
        self.buttonMsg.place(relx = 0.55,
                             rely = 0.008,
                             relheight = 0.06, 
                             relwidth = 0.22)
          
        self.buttonMsg.config(cursor = "arrow")

        # create a number writing button
        self.buttonWrite = Button(self.labelBottom,
                                text = "Write Number",
                                font = "Helvetica 10 bold", 
                                width = 20,
                                bg = "#ABB2B9",
                                command = lambda : self.writingPad())
          
        self.buttonWrite.place(relx = 0.77,
                             rely = 0.008,
                             relheight = 0.06, 
                             relwidth = 0.22)
          
        self.buttonWrite.config(cursor = "arrow")
          
        # create a scroll bar
        scrollbar = Scrollbar(self.textCons)
          
        # place the scroll bar 
        # into the gui window
        scrollbar.place(relheight = 1,
                        relx = 0.974)
          
        scrollbar.config(command = self.textCons.yview)
          
        self.textCons.config(state = DISABLED)
        
        # show the pet window
        self.add_desktop_pet()
    
    def add_desktop_pet(self):
        resize_width, resize_height = 64, 64
        pet_gif_path = "pet.gif"
        self.pet_gif = Image.open(pet_gif_path)

        # Load original frames and mirrored frames
        self.pet_frames_right = [
            ImageTk.PhotoImage(
                frame.copy().convert("RGBA").resize((resize_width, resize_height), Image.Resampling.LANCZOS)
            )
            for frame in ImageSequence.Iterator(self.pet_gif)
        ]
        self.pet_frames_left = [
            ImageTk.PhotoImage(
                ImageOps.mirror(
                    frame.copy().convert("RGBA").resize((resize_width, resize_height), Image.Resampling.LANCZOS)
                )
            )
            for frame in ImageSequence.Iterator(self.pet_gif)
        ]

        # Start with right-facing frames
        self.pet_frames = self.pet_frames_right
        self.pet_frame_index = 0
        self.pet_direction = 1  # 1 for right, -1 for left
        self.pet_speed = 2
        self.pet_x_pos = 0

        # Add to writing_window
        self.pet_label = Label(self.writing_window, bg="#FFF1F3", bd=0, highlightthickness=0)
        self.writing_window.update_idletasks()

        window_height = self.writing_window.winfo_height()
        pet_height = resize_height
        margin_from_bottom = 140

        pet_y = window_height - pet_height - margin_from_bottom
        pet_x = self.writing_window.winfo_width() - resize_width - 20  # Right side

        self.pet_label.place(x=pet_x, y=pet_y, width=resize_width, height=resize_height)

        self.animate_pet()
        self.pet_label.bind("<Button-1>", self.start_drag)
        self.pet_label.bind("<B1-Motion>", self.do_drag)
          
    def animate_pet(self):
        frame = self.pet_frames[self.pet_frame_index]
        self.pet_label.config(image=frame)

        self.pet_frame_index = (self.pet_frame_index + 1) % len(self.pet_frames)

        # Move pet left/right
        container_width = self.labelBottom.winfo_width()
        pet_width = self.pet_label.winfo_width()
        max_x = container_width - pet_width - 20

        self.pet_x_pos += self.pet_speed * self.pet_direction

        # Bounce logic
        if self.pet_x_pos >= max_x:
            self.pet_x_pos = max_x
            self.pet_direction = -1
            self.pet_frames = self.pet_frames_left
        elif self.pet_x_pos <= 20:
            self.pet_x_pos = 20
            self.pet_direction = 1
            self.pet_frames = self.pet_frames_right

        self.pet_label.place(x=self.pet_x_pos, rely=0.07)

        self.writing_window.after(100, self.animate_pet)

    def start_drag(self, event):
        self._drag_start_x = event.x_root - self.pet_label.winfo_x()
        self._drag_start_y = event.y_root - self.pet_label.winfo_y()

    def do_drag(self, event):
        x = event.x_root - self._drag_start_x
        y = event.y_root - self._drag_start_y
        self.pet_label.place(x=x, y=y)


    # function to basically start the thread for sending messages
    def sendButton(self, msg):
        self.textCons.config(state = DISABLED)
        self.my_msg = msg
        # print(msg)
        self.entryMsg.delete(0, END)
        
    def proc(self):
        while True:
            read, _, _ = select.select([self.socket], [], [], 0.1)
            peer_msg = []
            if self.socket in read:
                with socket_lock:
                    peer_msg = self.recv()

            if len(self.my_msg) > 0 or len(peer_msg) > 0:
                output = self.sm.proc(self.my_msg, peer_msg)
                self.my_msg = ""  # 清空输入消息
                if output:        # 仅在有输出时插入
                    self.textCons.config(state=NORMAL)
                    self.textCons.insert(END, output + "\n\n")
                    self.textCons.config(state=DISABLED)
                    self.textCons.see(END)



    def writingPad(self):
        self.writing_window = Toplevel()
        self.writing_window.title("WRITINGPAD")
        self.writing_window.resizable(width = False,
                              height = False)
        self.writing_window.configure(width = 300,
                              height = 400,
                              bg = "#17202A")
        self.write()
        
        self.clearButton = Button(self.writing_window,
                                text = "Clear",
                                font = "Helvetica 10 bold", 
                                width = 20,
                                bg = "#ABB2B9",
                                command = lambda : self.clear())

        self.clearButton.place(relx = 0.05,
                             rely = 0.85,
                             relheight = 0.1, 
                             relwidth = 0.3)
        
        self.textCons.config(cursor = "arrow")
          
        self.submitButton = Button(self.writing_window,
                                text = "Submit",
                                font = "Helvetica 10 bold", 
                                width = 20,
                                bg = "#ABB2B9",
                                command = lambda : self.submit())
        
        self.submitButton.place(relx = 0.40,
                             rely = 0.85,
                             relheight = 0.1, 
                             relwidth = 0.3)
        
        self.textCons.config(cursor = "arrow")

        self.resultLabel = Label(self.writing_window, 
                            text="", 
                            font=("Helvetica 10 bold"), 
                            bg="#ABB2B9")
        
        self.resultLabel.place(relx = 0.75,
                            rely = 0.85,
                            relheight = 0.1, 
                            relwidth = 0.2)
    
    def write(self):
        self.canvas = Canvas(self.writing_window, 
                            width=280, height=280, 
                            bg="white", 
                            cursor="cross")
        self.canvas.place(relx=0.033, rely=0.05)

        self.canvas.bind("<Button-1>", self.start_draw)
        self.canvas.bind("<B1-Motion>", self.draw)

    def start_draw(self, event):
        self.last_x, self.last_y = event.x, event.y

    def draw(self, event):
        self.canvas.create_line(self.last_x, self.last_y, event.x, event.y,
                                width=8, fill='black', capstyle=ROUND, smooth=True)
        self.last_x, self.last_y = event.x, event.y

    def clear(self):
        self.canvas.delete("all")

    def submit(self):

        # Get canvas position relative to screen
        x = self.writing_window.winfo_rootx() + self.canvas.winfo_x()
        y = self.writing_window.winfo_rooty() + self.canvas.winfo_y()
        x1 = x + self.canvas.winfo_width()
        y1 = y + self.canvas.winfo_height()

        # Capture image from screen
        img = ImageGrab.grab().crop((x, y, x1, y1)).convert("L")  # convert to grayscale

        # Invert colors: white background, black digit
        img = ImageOps.invert(img)

        # Resize to 28x28 for model input
        img = img.resize((28, 28))

        predicted_digit = send_image(img, self.socket)  # Call the client-side request
        self.resultLabel.config(text = f"{predicted_digit}")

    def run(self):
        self.login()

# create a GUI class object
if __name__ == "__main__": 
    g = GUI()
