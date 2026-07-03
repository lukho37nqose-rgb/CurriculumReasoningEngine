css_file = 'static/app.css'
with open(css_file, 'r') as f:
    content = f.read()

# I will define standard classes for the layout instead of inline styles

new_css = """.hero-actions{display:flex;align-items:center;gap:14px;margin-top:34px;flex-wrap:wrap}.hero-options{display:flex;flex-direction:column;align-items:flex-start;gap:16px;margin-top:34px;width:100%;max-width:480px}.onboarding-option{border:1px solid var(--line);border-radius:var(--radius-sm);padding:16px;background:white;width:100%}.onboarding-option h3{margin:0 0 8px;font-family:var(--serif);font-size:18px;color:var(--forest)}.onboarding-option h3 span{font-size:13px;color:var(--forest-3);font-family:var(--sans);font-weight:normal}.onboarding-option p{margin:0 0 16px;font-size:14px;color:var(--muted)}.primary-action"""

content = content.replace(".hero-actions{display:flex;align-items:center;gap:14px;margin-top:34px;flex-wrap:wrap}.primary-action", new_css)

with open(css_file, 'w') as f:
    f.write(content)
