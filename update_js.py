import re

js_file = 'static/app.js'

with open(js_file, 'r') as f:
    content = f.read()

# Instead of exploreMethodButton, the ID was replaced in HTML.
# But we still need exploreMethodButton to work if it's referenced in JS.
# Or we can map exploreButton to show the modal (as that makes sense for "Explore")
# And let's wire buildManuallyButton to also show the dialog or do nothing safely.

if 'exploreMethodButton' in content and 'exploreButton' not in content:
    content = content.replace('exploreMethodButton', 'exploreButton')

with open(js_file, 'w') as f:
    f.write(content)
