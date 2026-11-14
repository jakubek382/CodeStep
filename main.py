"""CodeStep - learn to code step by step (13 languages)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from codestep.ui.app import App  # noqa: E402

if __name__ == "__main__":
    App().mainloop()
