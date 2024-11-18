import gi
import requests
import json
import os
import threading

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
from gi.repository import Adw, Gtk, Gdk, GLib


class ChatApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.example.ChatApp")
        self.window = None
        self.conversations_file = os.path.expanduser("~/.ollama_chat/conversations.json")

    def do_activate(self):
        if not self.window:
            self.window = ChatWindow(application=self)
        self.window.present()

    def do_shutdown(self):
        """Save conversations to a file when the app is closed."""
        if self.window:
            self.window.save_conversations()
        super().do_shutdown()  # Chain up to the superclass shutdown method


class ChatWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_default_size(800, 600)

        # Connect the close-request signal to handle the 'X' button click
        self.connect("close-request", self.on_close_request)

        # Load CSS Styles
        self.load_css()

        # Main content layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        main_box.set_margin_top(10)
        main_box.set_margin_bottom(10)
        main_box.set_margin_start(10)
        main_box.set_margin_end(10)

        # Sidebar for conversation list
        self.sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.sidebar.set_margin_start(10)
        self.sidebar.set_margin_top(10)
        self.sidebar.set_margin_bottom(10)
        self.sidebar.set_hexpand(False)

        # Add "New Conversation" button to sidebar
        new_conversation_button = Gtk.Button(label="➕ New Conversation")
        new_conversation_button.connect("clicked", self.start_new_conversation)
        self.sidebar.append(new_conversation_button)

        # Load saved conversations from file
        self.saved_conversations = self.load_conversations()
        self.conversation_listbox = Gtk.ListBox()
        self.sidebar.append(self.conversation_listbox)

        # Connect selection of a conversation
        self.conversation_listbox.connect("row-activated", self.load_conversation)
        self.update_sidebar()

        # Right-side content (chat UI)
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Header Bar using Libadwaita
        header_bar = Adw.HeaderBar()
        header_bar.set_title_widget(Gtk.Label(label="FennecOs Assistant"))
        right_box.append(header_bar)

        # Chat display area (scrollable)
        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.text_buffer = self.text_view.get_buffer()

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(self.text_view)
        scroll.set_vexpand(True)
        right_box.append(scroll)

        # Bottom box for input and button
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        bottom_box.set_margin_top(5)

        # Input field
        self.input_field = Gtk.Entry()
        self.input_field.set_placeholder_text("Type your prompt here...")
        self.input_field.set_hexpand(True)

        # Send button
        self.send_button = Gtk.Button(label="Ask!")
        self.send_button.connect("clicked", self.on_send_click)

        bottom_box.append(self.input_field)
        bottom_box.append(self.send_button)
        right_box.append(bottom_box)

        # Add sidebar and right content to main layout
        main_box.append(self.sidebar)
        main_box.append(right_box)

        # Set content
        self.set_content(main_box)

        # Set initial conversation
        self.current_conversation = self.saved_conversations[0] if self.saved_conversations else []
        self.display_conversation(self.current_conversation)

    def load_css(self):
        """Load and apply the CSS file."""
        css_provider = Gtk.CssProvider()
        css_content = """
        window {
            background: linear-gradient(to bottom, #f4e3c1, #d2b48c); /* Sahara tones */
        }
        textview {
            background: #fff7e6; /* Light sand */
            color: #3e2f2c; /* Darker text */
            border: 2px solid #c19a6b; /* Desert brown border */
            border-radius: 8px;
        }
        entry {
            background: #fff7e6; /* Light sand */
            color: #3e2f2c; /* Darker text */
            border: 2px solid #8b4513; /* Darker desert brown */
            border-radius: 8px;
            padding: 5px;
        }
        button {
            background: #cd853f; /* Sandy orange */
            color: white;
            border-radius: 8px;
            padding: 8px;
            font-weight: bold;
        }
        button:hover {
            background: #a0522d; /* Darker sandy orange */
        }
        """
        css_provider.load_from_data(css_content.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def start_new_conversation(self, button):
        """Start a new conversation by creating a blank conversation."""
        self.saved_conversations.append([])
        self.update_sidebar()
        self.current_conversation = []
        self.text_buffer.set_text("")

    def update_sidebar(self):
        """Update the sidebar with saved conversations."""
        child = self.conversation_listbox.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.conversation_listbox.remove(child)
            child = next_child

        for idx, conversation in enumerate(self.saved_conversations):
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=f"💬 Conversation {idx + 1}")
            row.set_child(label)
            self.conversation_listbox.append(row)

        self.conversation_listbox.queue_draw()

    def load_conversation(self, listbox, row):
        """Load a selected conversation."""
        index = row.get_index()
        if 0 <= index < len(self.saved_conversations):
            self.current_conversation = self.saved_conversations[index]
            self.display_conversation(self.current_conversation)

    def display_conversation(self, conversation):
        """Display a conversation in the text view."""
        self.text_buffer.set_text("\n".join(conversation))

    def on_send_click(self, button):
        """Handle the Send button click."""
        user_input = self.input_field.get_text()
        if not user_input.strip():
            return

        # Disable the button to prevent multiple clicks
        self.send_button.set_sensitive(False)

        # Add user input to the conversation
        self.add_to_conversation(f"You: {user_input}\nAI: ")

        # Clear the input field
        self.input_field.set_text("")

        # Send the prompt to Ollama and display AI response
        self.query_ollama_streaming(user_input)

    def query_ollama_streaming(self, prompt):
        """Send a prompt to the Ollama server in a separate thread."""
        def fetch_response():
            url = "http://localhost:11434/api/generate"
            headers = {"Content-Type": "application/json"}
            payload = {"model": "llama3.2", "prompt": prompt, "stream": True}

            try:
                response = requests.post(url, headers=headers, data=json.dumps(payload), stream=True)
                response.raise_for_status()

                ai_response = ""
                for chunk in response.iter_lines():
                    if chunk:
                        data = json.loads(chunk.decode("utf-8"))
                        part = data.get("response", "")
                        ai_response += part
                        GLib.idle_add(self.update_ai_response, ai_response)
            except requests.exceptions.RequestException as e:
                GLib.idle_add(self.add_to_conversation, f"Error: {e}")
            finally:
                GLib.idle_add(self.send_button.set_sensitive, True)

        threading.Thread(target=fetch_response, daemon=True).start()

    def update_ai_response(self, text):
        """Update the AI response line dynamically."""
        start_iter = self.text_buffer.get_start_iter()
        end_iter = self.text_buffer.get_end_iter()
        existing_text = self.text_buffer.get_text(start_iter, end_iter, True)

        # Update only the last line for the AI response
        if "AI:" in existing_text:
            new_text = existing_text[:existing_text.rindex("AI:") + 4] + text
        else:
            new_text = existing_text + text

        self.text_buffer.set_text(new_text)

    def add_to_conversation(self, text):
        """Add text to the current conversation."""
        self.current_conversation.append(text)
        self.display_conversation(self.current_conversation)

    def save_conversations(self):
        """Save all conversations to a JSON file."""
        def save():
            app = self.get_application()
            conversations_file = app.conversations_file if app else os.path.expanduser("~/.ollama_chat/conversations.json")
            os.makedirs(os.path.dirname(conversations_file), exist_ok=True)
            with open(conversations_file, "w") as f:
                json.dump(self.saved_conversations, f, indent=2)

        threading.Thread(target=save, daemon=True).start()

    def load_conversations(self):
        """Load conversations from a JSON file."""
        app = self.get_application()
        if os.path.exists(app.conversations_file):
            try:
                with open(app.conversations_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                print("Failed to load conversations. Starting with an empty list.")
        return []

    def on_close_request(self, window):
        """Handle the 'X' button click."""
        print("Closing the window and saving conversations...")
        self.save_conversations()
        return False  # Allow the default close behavior


if __name__ == "__main__":
    app = ChatApp()
    app.run()
