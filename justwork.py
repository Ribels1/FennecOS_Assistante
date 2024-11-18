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
        super().do_shutdown()


class ChatWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_default_size(900, 600)

        # Connect the close-request signal to handle the 'X' button click
        self.connect("close-request", self.on_close_request)

        # Load CSS Styles
        self.load_css()

        # Main content layout
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        main_box.set_margin_top(10)
        main_box.set_margin_bottom(10)
        main_box.set_margin_start(10)
        main_box.set_margin_end(10)

        # Sidebar for conversation list
        self.sidebar = Adw.PreferencesGroup()
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        sidebar_box.set_margin_top(10)
        sidebar_box.set_margin_bottom(10)
        sidebar_box.set_margin_start(10)
        sidebar_box.set_margin_end(10)

        # Add "New Conversation" button to sidebar
        new_conversation_button = Gtk.Button(label="➕ New Conversation")
        new_conversation_button.set_halign(Gtk.Align.CENTER)
        new_conversation_button.add_css_class("suggested-action")  # Highlight the button
        new_conversation_button.connect("clicked", self.start_new_conversation)
        sidebar_box.append(new_conversation_button)

        # Conversation list
        self.saved_conversations = self.load_conversations()
        self.conversation_listbox = Gtk.ListBox()
        self.conversation_listbox.set_vexpand(True)
        self.conversation_listbox.connect("row-activated", self.load_conversation)
        sidebar_box.append(self.conversation_listbox)

        self.update_sidebar()
        self.sidebar.add(sidebar_box)
        main_box.append(self.sidebar)

        # Right-side content (chat UI)
        right_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Header Bar using Libadwaita
        header_bar = Adw.HeaderBar()
        header_bar.set_title_widget(Gtk.Label(label="FennecOs Assistant"))
        header_bar.add_css_class("title")
        right_box.append(header_bar)

        # Chat display area (scrollable)
        self.chat_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.chat_box.set_vexpand(True)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_child(self.chat_box)
        right_box.append(scroll)

        # Bottom box for input and button
        bottom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        bottom_box.set_margin_top(5)

        # Input field
        self.input_field = Gtk.Entry()
        self.input_field.set_placeholder_text("Type your prompt here...")
        self.input_field.set_hexpand(True)

        # Send button
        self.send_button = Gtk.Button(label="Ask!")
        self.send_button.connect("clicked", self.on_send_click)
        self.send_button.add_css_class("suggested-action")

        bottom_box.append(self.input_field)
        bottom_box.append(self.send_button)
        right_box.append(bottom_box)

        # Add sidebar and right content to main layout
        main_box.append(right_box)

        # Set content
        self.set_content(main_box)

        # Set initial conversation
        self.current_index = 0 if self.saved_conversations else -1
        self.current_conversation = self.saved_conversations[0] if self.saved_conversations else []
        self.display_conversation(self.current_conversation)

    def load_css(self):
        """Load and apply the CSS file."""
        css_provider = Gtk.CssProvider()
        css_content = """
        window {
            background: linear-gradient(to bottom, #f7f2e7, #dbcba9);
        }
        .user-message {
            background: #e8f5e9;
            color: #3e2f2c;
            padding: 8px;
            margin: 5px;
            border-radius: 8px;
        }
        .ai-message {
            background: #e3f2fd;
            color: #3e2f2c;
            padding: 8px;
            margin: 5px;
            border-radius: 8px;
        }
        button {
            background: #cd853f;
            color: white;
            border-radius: 8px;
            font-weight: bold;
        }
        button:hover {
            background: #a0522d;
        }
        button.destructive-action {
            background: white;
            color: gray;
        }
        button.destructive-action:hover {
            background: #f0827f;
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
        self.current_conversation = []
        self.saved_conversations.append(self.current_conversation)
        self.current_index = len(self.saved_conversations) - 1
        self.update_sidebar()
        child = self.chat_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.chat_box.remove(child)
            child = next_child
        # self.chat_box.foreach(lambda widget: widget.destroy())
        self.save_conversations()

    def update_sidebar(self):
        """Update the sidebar with saved conversations."""
        child = self.conversation_listbox.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.conversation_listbox.remove(child)
            child = next_child

        for idx, conversation in enumerate(self.saved_conversations):
            row = Gtk.ListBoxRow()
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

            label = Gtk.Label(label=f"💬 Conversation {idx + 1}")
            label.set_xalign(0)
            row_box.append(label)

            delete_button = Gtk.Button(icon_name="user-trash-symbolic")
            delete_button.set_tooltip_text("Delete this conversation")
            delete_button.add_css_class("destructive-action")
            delete_button.connect("clicked", self.delete_conversation, idx)
            row_box.append(delete_button)

            row.set_child(row_box)
            self.conversation_listbox.append(row)

        self.conversation_listbox.queue_draw()

    def delete_conversation(self, button, index):
        """Delete a conversation."""
        if 0 <= index < len(self.saved_conversations):
            del self.saved_conversations[index]
        self.save_conversations()
        self.update_sidebar()

    def load_conversation(self, listbox, row):
        """Load a selected conversation."""
        self.current_index = row.get_index()
        self.current_conversation = self.saved_conversations[self.current_index]
        self.display_conversation(self.current_conversation)

    def display_conversation(self, conversation):
        """Display a conversation in the chat box."""
        # self.chat_box.foreach(lambda widget: widget.destroy())
        child = self.chat_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.chat_box.remove(child)
            child = next_child
        for message in conversation:
            css_class = "user-message" if message.startswith("You:") else "ai-message"
            self.add_message(message, css_class)

    def on_send_click(self, button):
        """Handle the Send button click."""
        user_input = self.input_field.get_text()
        if not user_input.strip():
            return

        # Disable the button to prevent multiple clicks
        self.send_button.set_sensitive(False)

        # Add user input to the conversation
        self.add_message(f"You: {user_input}", "user-message")
        self.current_conversation.append(f"You: {user_input}")

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

                ai_response_label = self.add_message("AI: ", "ai-message")
                ai_response_text = ""

                for chunk in response.iter_lines():
                    if chunk:
                        data = json.loads(chunk.decode("utf-8"))
                        part = data.get("response", "")
                        ai_response_text += part
                        GLib.idle_add(self.update_ai_response, ai_response_label, ai_response_text)

                GLib.idle_add(self.finalize_ai_response, ai_response_text)
            except requests.exceptions.RequestException as e:
                GLib.idle_add(self.add_message, f"Error: {e}", "ai-message")
            finally:
                GLib.idle_add(self.send_button.set_sensitive, True)

        threading.Thread(target=fetch_response, daemon=True).start()

    def update_ai_response(self, label, text):
        """Update the AI response label dynamically."""
        label.set_label(text)

    def finalize_ai_response(self, full_response):
        """Finalize and save the full AI response."""
        self.current_conversation.append(f"AI: {full_response}")
        self.save_conversations()

    def add_message(self, text, css_class):
        """Add a single message to the chat box with a specific CSS class."""
        message_label = Gtk.Label(label=text)
        message_label.add_css_class(css_class)
        message_label.set_wrap(True)
        message_label.set_xalign(0)
        self.chat_box.append(message_label)
        self.chat_box.show()
        return message_label

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
        return False


if __name__ == "__main__":
    app = ChatApp()
    app.run()
