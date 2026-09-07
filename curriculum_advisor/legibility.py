"""Display-only descriptions of existing governed curriculum metadata."""


def requirement_instructions(rule, course_names):
    def course(code):
        name = course_names.get(code)
        return f"{code} - {name}" if name else code

    codes = rule.get("course_codes", [])
    names = "; ".join(course(code) for code in codes)
    kind = rule.get("type")
    if kind == "all_courses":
        return f"Complete every listed course: {names}."
    if kind == "course":
        if len(codes) == 1:
            return f"Complete {names}."
        required = rule.get("required", 1)
        count = "one course" if required == 1 else f"{required} courses"
        return f"Complete {count} from this group: {names}."
    if kind == "credit_pool":
        return f"Complete at least {rule['required']} credits from this group: {names}."
    if kind == "choose_n":
        options = " ".join(
            f"{child.get('label', 'Option')}: {requirement_instructions(child, course_names)}"
            for child in rule.get("children", [])
        )
        return f"Complete at least {rule['required']} of these preparation options. {options}"
    return rule.get("label", "The represented requirement is described in its source.")
