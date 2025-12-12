from google.genai import types
import sys

print([x for x in dir(types) if 'Image' in x or 'Config' in x])

