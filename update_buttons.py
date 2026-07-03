import re

html_file = 'static/index.html'

with open(html_file, 'r') as f:
    content = f.read()

# Add empty hrefs and IDs for the new buttons so they look clickable
# Note: Since Option B and C are currently non-functional stubs based on the design provided,
# they shouldn't trigger an error, just act as dummy buttons or open the dialog
# The user issue mentions:
# "Option A ... Option B ... Option C ..."

content = content.replace(
    '<button class="secondary-action" type="button">Build manually</button>',
    '<button class="secondary-action" type="button" id="buildManuallyButton">Build manually</button>'
)

content = content.replace(
    '<button class="secondary-action" type="button">Explore</button>',
    '<button class="secondary-action" type="button" id="exploreButton">Explore</button>'
)

with open(html_file, 'w') as f:
    f.write(content)
