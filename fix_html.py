html_file = 'static/index.html'
with open(html_file, 'r') as f:
    content = f.read()

content = content.replace(
    '<div class="hero-actions" style="flex-direction: column; align-items: flex-start; gap: 16px;">',
    '<div class="hero-options">'
)
content = content.replace(
    '<div class="onboarding-option" style="border: 1px solid var(--line); border-radius: var(--radius-sm); padding: 16px; background: white; width: 100%;">',
    '<div class="onboarding-option">'
)
content = content.replace(
    '<h3 style="margin: 0 0 8px; font-family: var(--serif); font-size: 18px; color: var(--forest);">Option A: Speedrun with a Transcript <span style="font-size: 13px; color: var(--forest-3); font-family: var(--sans);">(Recommended if you have one)</span></h3>',
    '<h3>Option A: Speedrun with a Transcript <span>(Recommended if you have one)</span></h3>'
)
content = content.replace(
    '<p style="margin: 0 0 16px; font-size: 14px; color: var(--muted);">Upload your latest academic record to instantly build your profile. You can edit it afterward.</p>',
    '<p>Upload your latest academic record to instantly build your profile. You can edit it afterward.</p>'
)
content = content.replace(
    '<h3 style="margin: 0 0 8px; font-family: var(--serif); font-size: 18px; color: var(--forest);">Option B: Build from Memory</h3>',
    '<h3>Option B: Build from Memory</h3>'
)
content = content.replace(
    '<p style="margin: 0 0 16px; font-size: 14px; color: var(--muted);">Don\'t have your record? No problem. Tell us what degree you are doing and what courses you\'ve taken.</p>',
    '<p>Don\'t have your record? No problem. Tell us what degree you are doing and what courses you\'ve taken.</p>'
)
content = content.replace(
    '<h3 style="margin: 0 0 8px; font-family: var(--serif); font-size: 18px; color: var(--forest);">Option C: Just Exploring</h3>',
    '<h3>Option C: Just Exploring</h3>'
)
content = content.replace(
    '<p style="margin: 0 0 16px; font-size: 14px; color: var(--muted);">Start with a blank slate to see how a degree is structured.</p>',
    '<p>Start with a blank slate to see how a degree is structured.</p>'
)

with open(html_file, 'w') as f:
    f.write(content)
