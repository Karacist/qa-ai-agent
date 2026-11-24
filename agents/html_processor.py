import re
from typing import Any, Dict, List


def clean_html_for_llm(html: str, max_chars: int = 12000) -> str:
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
    html = re.sub(r'\s+', ' ', html)
    return html[:max_chars].strip()


def extract_page_structure(html: str) -> Dict[str, Any]:
    structure: Dict[str, Any] = {
        "forms": [],
        "buttons": [],
        "links": [],
        "headings": [],
        "inputs": [],
        "images_without_alt": 0,
        "select_elements": [],
    }

    # Forms with fields
    for fm in re.finditer(r'<form([^>]*)>(.*?)</form>', html, re.DOTALL | re.IGNORECASE):
        attrs, body = fm.group(1), fm.group(2)
        action_m = re.search(r'action=["\']([^"\']*)["\']', attrs)
        method_m = re.search(r'method=["\']([^"\']*)["\']', attrs)
        fields: List[Dict] = []

        for inp in re.finditer(r'<input([^>]*)/?>', body, re.IGNORECASE):
            ia = inp.group(1)
            t_m = re.search(r'type=["\']([^"\']*)["\']', ia)
            n_m = re.search(r'name=["\']([^"\']*)["\']', ia)
            p_m = re.search(r'placeholder=["\']([^"\']*)["\']', ia)
            id_m = re.search(r'\bid=["\']([^"\']*)["\']', ia)
            fields.append({
                "type": t_m.group(1) if t_m else "text",
                "name": n_m.group(1) if n_m else "",
                "placeholder": p_m.group(1) if p_m else "",
                "id": id_m.group(1) if id_m else "",
                "required": bool(re.search(r'\brequired\b', ia, re.IGNORECASE)),
            })

        for ta in re.finditer(r'<textarea([^>]*)>', body, re.IGNORECASE):
            ta_a = ta.group(1)
            n_m = re.search(r'name=["\']([^"\']*)["\']', ta_a)
            id_m = re.search(r'\bid=["\']([^"\']*)["\']', ta_a)
            fields.append({
                "type": "textarea",
                "name": n_m.group(1) if n_m else "",
                "placeholder": "",
                "id": id_m.group(1) if id_m else "",
                "required": bool(re.search(r'\brequired\b', ta_a, re.IGNORECASE)),
            })

        structure["forms"].append({
            "action": action_m.group(1) if action_m else "",
            "method": method_m.group(1) if method_m else "get",
            "fields": fields,
        })

    # All inputs (outside forms too)
    for inp in re.finditer(r'<input([^>]*)/?>', html, re.IGNORECASE):
        ia = inp.group(1)
        t_m = re.search(r'type=["\']([^"\']*)["\']', ia)
        n_m = re.search(r'name=["\']([^"\']*)["\']', ia)
        id_m = re.search(r'\bid=["\']([^"\']*)["\']', ia)
        p_m = re.search(r'placeholder=["\']([^"\']*)["\']', ia)
        structure["inputs"].append({
            "type": t_m.group(1) if t_m else "text",
            "name": n_m.group(1) if n_m else "",
            "id": id_m.group(1) if id_m else "",
            "placeholder": p_m.group(1) if p_m else "",
        })

    # Buttons
    for bm in re.finditer(r'<button([^>]*)>(.*?)</button>', html, re.DOTALL | re.IGNORECASE):
        text = re.sub(r'<[^>]+>', '', bm.group(2)).strip()[:100]
        if text:
            bt = re.search(r'type=["\']([^"\']*)["\']', bm.group(1))
            id_m = re.search(r'\bid=["\']([^"\']*)["\']', bm.group(1))
            cls_m = re.search(r'class=["\']([^"\']*)["\']', bm.group(1))
            structure["buttons"].append({
                "text": text,
                "type": bt.group(1) if bt else "button",
                "id": id_m.group(1) if id_m else "",
                "class": cls_m.group(1) if cls_m else "",
            })

    # Headings
    for hm in re.finditer(r'<h([1-6])([^>]*)>(.*?)</h\1>', html, re.DOTALL | re.IGNORECASE):
        text = re.sub(r'<[^>]+>', '', hm.group(3)).strip()[:200]
        if text:
            structure["headings"].append({"level": int(hm.group(1)), "text": text})

    # Links
    for am in re.finditer(r'<a([^>]*)>(.*?)</a>', html, re.DOTALL | re.IGNORECASE):
        href = re.search(r'href=["\']([^"\']*)["\']', am.group(1))
        text = re.sub(r'<[^>]+>', '', am.group(2)).strip()[:100]
        if href and text:
            structure["links"].append({"href": href.group(1), "text": text})

    # Select elements
    for sel in re.finditer(r'<select([^>]*)>(.*?)</select>', html, re.DOTALL | re.IGNORECASE):
        n_m = re.search(r'name=["\']([^"\']*)["\']', sel.group(1))
        options = re.findall(r'<option[^>]*>([^<]+)</option>', sel.group(2), re.IGNORECASE)
        structure["select_elements"].append({
            "name": n_m.group(1) if n_m else "",
            "options": [o.strip() for o in options[:10]],
        })

    # Images without alt
    structure["images_without_alt"] = sum(
        1 for _ in re.finditer(r'<img(?![^>]*\balt\s*=)[^>]*>', html, re.IGNORECASE)
    )

    return structure
