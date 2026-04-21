#!/usr/bin/env python3
"""
parse_linkedin_archive_v4.py

Parses a zipped LinkedIn profile save ("Webpage, Complete" → ArchiveXXX.zip) offline
and emits JSON in this schema:

{
  "fullName": "",
  "headline": "",
  "location": "",
  "profileUrl": "",
  "photoUrl": "",
  "about": "",
  "positions": [
    {"title": "", "company": "", "location": "", "startDate": "", "endDate": null, "description": ""}
  ],
  "education": [
    {"school": "", "degree": "", "field": "", "startDate": "", "endDate": ""}
  ],
  "skills": [],
  "certifications": [],
  "websites": []
}

Notes:
- Works entirely offline on your saved HTML; no live web calls.
- **fullName** & **headline** logic is EXACTLY as requested (lockup classes first).
- About: prefers the full text in <span class="visually-hidden">, falls back to visible aria-hidden.
- Location: targets <span class="text-body-small inline t-black--light break-words"> and nearby top-card elements.
- Websites: prefers <section class="pv-top-card--website"> anchor hrefs, then falls back to other external links.
- Positions/Education/Skills/Certifications: heuristic extraction (can be tightened with more DOM samples).

Usage:
  python parse_linkedin_archive_v4.py /path/to/ArchiveXXX.zip /path/to/out.json
"""

import sys, zipfile, pathlib, json, re, tempfile
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup, Comment

# -------------------- helpers --------------------

def txt(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def get_meta(soup: BeautifulSoup, prop: str) -> str:
    tag = soup.find("meta", attrs={"property": prop})
    return txt(tag["content"]) if tag and tag.get("content") else ""




import re
from bs4 import BeautifulSoup

def get_profile_url(soup: BeautifulSoup) -> str:
    """
    Resolve the canonical LinkedIn profile URL from an archived page.
    Priority:
      1) <meta property="og:url"> or <link rel="canonical">
      2) Top-card anchors (Contact info, About this profile, any /in/ inside top card)
      3) Any other /in/ links, with scoring that prefers top-card proximity and exactness
    Normalization:
      - strip query/fragment
      - remove /overlay/*, /details/*, /featured/*, /recent-activity/*
      - force https
      - drop trailing slash
    """
    def _txt(s): return re.sub(r"\s+", " ", (s or "").strip())

    def _clean(u: str) -> str:
        if not u:
            return ""
        u = re.sub(r"[?#].*$", "", u)  # drop query/fragment
        u = re.sub(r"/(?:overlay|details|featured|recent-activity)(?:/.*)?$", "", u, flags=re.I)
        u = re.sub(r"^http:", "https:", u, flags=re.I)
        return u.rstrip("/")

    # --- 1) og:url / canonical ---
    m = soup.find("meta", attrs={"property": "og:url"}) or soup.find("meta", attrs={"name": "og:url"})
    if m and m.get("content"):
        return _clean(_txt(m["content"]))

    def _has_canonical(val):
        if val is None: return False
        if isinstance(val, (list, tuple, set)):
            return any(str(v).lower() == "canonical" for v in val)
        return "canonical" in str(val).lower()

    can = soup.find("link", attrs={"rel": _has_canonical})
    if can and can.get("href"):
        return _clean(_txt(can["href"]))

    # --- 2) Prefer top-card anchors ---
    def _to_abs(href: str) -> str:
        return ("https://www.linkedin.com" + href) if href and href.startswith("/in/") else href

    # a) Contact info anchor in the top card
    a = soup.select_one('a#top-card-text-details-contact-info[href*="/in/"]')
    if a and a.get("href"):
        return _clean(_to_abs(a["href"].strip()))

    # b) The name anchor with aria-label equal to the profile name (overlay/about-this-profile)
    try:
        from bs4 import BeautifulSoup  # noqa: F401  (ensure BS present)
        # get_name is defined elsewhere in your script; use it if available
        name = ""
        try:
            name = get_name(soup)  # type: ignore[name-defined]
        except Exception:
            # fallback: read the H1 text directly
            h1 = soup.find("h1")
            name = _txt(h1.get_text(" ")) if h1 else ""
        if name:
            a = soup.find("a", href=True, attrs={"aria-label": re.compile(rf"^{re.escape(name)}$", re.I)})
            if a and "/in/" in a.get("href", ""):
                return _clean(_to_abs(a["href"].strip()))
    except Exception:
        pass

    # c) Any /in/ link inside the top-card section (usually has data-member-id)
    top = soup.select_one("section[data-member-id]") or soup.select_one("section.pv-top-card") \
          or soup.select_one("section[class*='top-card']")
    if top:
        for a in top.select("a[href*='/in/']"):
            href = _to_abs(a.get("href", "").strip())
            if "/in/" in (href or ""):
                return _clean(href)

    # --- 3) Score any remaining /in/ links on the page ---
    candidates = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("blob:"):
            continue
        if "linkedin.com" not in href and not href.startswith("/in/"):
            continue
        href = _to_abs(href)
        if "/in/" not in href:
            continue

        raw = href  # keep raw for feature flags
        u = _clean(href)

        # features for scoring
        ancestor_text = " ".join((a.get_text(" ", strip=True) or "").split()).lower()
        is_contact = "contact info" in ancestor_text or "contact" in (a.get("id", "").lower())
        has_about_overlay = "/overlay/about-this-profile" in raw.lower()
        in_top = bool(a.find_parent("section", attrs={"data-member-id": True}))
        exact = bool(re.search(r"/in/[^/]+$", u, re.I))

        score = (
            0 if in_top else 1,
            0 if is_contact else 1,
            0 if has_about_overlay else 1,
            0 if exact else 1,
            len(u),
        )
        candidates.append((score, u))

    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    return ""









def _multiline(el: Optional[BeautifulSoup]) -> str:
    """Extract text preserving intended line breaks from <br> and block-ish spans."""
    if not el:
        return ""
    # Replace <br> with \n to preserve paragraphing
    for br in el.find_all("br"):
        br.replace_with("\n")
    raw = el.get_text("\n", strip=True)
    # Normalize: collapse >2 newlines to 2, trim lines
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    raw = "\n".join(line.rstrip() for line in raw.splitlines())
    return raw.strip()

# ===== DO NOT CHANGE: fullName & headline extraction =====

def clean_title_to_name(raw: str) -> str:
    # "(23) Name | LinkedIn" → "Name"
    raw = re.sub(r"^\(\d+\)\s*", "", raw)
    raw = raw.split("|")[0]
    raw = re.split(r"[-–|]", raw)[0]
    return txt(raw)

def get_name(soup: BeautifulSoup) -> str:
    # Prefer explicit lockup title, else og:title / <title>
    lock = soup.select_one(".artdeco-entity-lockup__title")
    if lock:
        return txt(lock.get_text(" "))
    title_tag = soup.find("title")
    raw = get_meta(soup, "og:title") or (txt(title_tag.get_text()) if title_tag else "")
    return clean_title_to_name(raw) if raw else ""

def get_headline(soup: BeautifulSoup) -> str:
    # Prefer lockup subtitle, else og:description, else common containers (skip "notifications" noise)
    sub = soup.select_one(".artdeco-entity-lockup__subtitle")
    if sub:
        return txt(sub.get_text(" "))
    ogd = get_meta(soup, "og:description")
    if ogd:
        return ogd
    for sel in [
        '.pv-text-details__left-panel h2',
        '.pv-text-details__left-panel .text-body-medium',
        '[data-test-id="hero-section"] h2',
        'h2'
    ]:
        el = soup.select_one(sel)
        if el:
            h = txt(el.get_text(" "))
            if not re.search(r"\bnotifications?\b", h, re.I):
                return h
    return ""

# ===== Location & Websites =====

def get_location(soup: BeautifulSoup) -> str:
    """
    Target the exact snippet provided:
      <span class="text-body-small inline t-black--light break-words">Bengaluru, Karnataka, India</span>
    Also check nearby 'top card' containers and meta description as fallback.
    """
    # 1) Exact class combo (order-insensitive)
    for span in soup.select("span.text-body-small.inline.t-black--light.break-words"):
        loc = txt(span.get_text(" "))
        if loc:
            return loc

    # 2) Nearby containers that often hold location
    for sel in [
        '.pv-text-details__left-panel .text-body-small',
        '.pv-text-details__left-panel',
        '[data-test-id="top-card-subline"]',
        '.top-card-layout__entity-info',
        'div.mt2'  # wrapper around location + "Contact info" link in your snippet
    ]:
        for el in soup.select(sel):
            span = el.select_one("span.text-body-small.inline.t-black--light.break-words") or el.find("span")
            if span:
                loc = txt(span.get_text(" "))
                if re.search(r"\b(India|Karnataka|Bengaluru|Bangalore)\b", loc, re.I) or "," in loc:
                    return loc

    # 3) meta description sometimes: "Name – Headline | Location | LinkedIn"
    mdesc = soup.find("meta", attrs={"name": "description"})
    if mdesc and mdesc.get("content"):
        desc = txt(mdesc["content"])
        parts = [p.strip() for p in desc.split("|") if p.strip()]
        for p in parts:
            if re.search(r"\b(India|Karnataka|Bengaluru|Bangalore)\b", p, re.I) or "," in p:
                return p

    return ""

def get_websites(soup: BeautifulSoup) -> List[str]:
    """
    Prefer websites inside the top-card website section:
      <section class="pv-top-card--website"> <a href="...">Label</a> </section>
    Fallback: collect external (non-LinkedIn) http(s) links elsewhere.
    """
    urls, seen = [], set()

    # 1) Top-card website section (preferred)
    for sec in soup.select("section.pv-top-card--website"):
        for a in sec.select("a[href]"):
            href = a["href"].strip()
            if href.lower().startswith(("http://", "https://")):
                low = href.lower()
                if "linkedin.com" not in low and low not in seen:
                    seen.add(low)
                    urls.append(href)

    # 2) Fallback: any external links on page
    if not urls:
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.lower().startswith(("http://", "https://")) and "linkedin.com" not in href.lower():
                low = href.lower()
                if low not in seen:
                    seen.add(low)
                    urls.append(href)

    return urls[:30]

# ===== About (precise, per your snippet) =====

def get_about(soup: BeautifulSoup) -> str:
    """
    Extract full About content:
      - Find the 'About' header: <h2 class="pvs-header__title">About</h2>
      - Locate the nearest 'inline-show-more-text' wrapper
      - Prefer <span class="visually-hidden"> (full text), else <span aria-hidden="true">
      - Convert <br> to real newlines and normalize whitespace
    """
    from bs4 import Comment
    import re

    def normalize_html(node):
        if not node:
            return ""
        # Preserve intended line breaks
        for br in node.find_all("br"):
            br.replace_with("\n")
        # Strip empty comment nodes like <!---->
        for c in node.find_all(string=lambda t: isinstance(t, Comment)):
            c.extract()
        text = node.get_text("\n", strip=True)
        # Cleanup
        text = text.replace("\xa0", " ")
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = "\n".join(line.rstrip() for line in text.splitlines())
        return text.strip()

    # 1) Find the 'About' header
    about_h2 = None
    for h2 in soup.select("h2.pvs-header__title"):
        label = " ".join(h2.stripped_strings).lower()
        if "about" in label:
            about_h2 = h2
            break
    if not about_h2:
        return ""

    # 2) Find the nearest inline-show-more-text wrapper after the header
    wrapper = about_h2.find_next("div", class_=re.compile(r"inline-show-more-text", re.I))
    if not wrapper:
        # Try a couple of ancestor scopes, then search within them
        parent = about_h2
        for _ in range(3):
            if parent.parent:
                parent = parent.parent
                wrapper = parent.find("div", class_=re.compile(r"inline-show-more-text", re.I))
                if wrapper:
                    break
    if not wrapper:
        return ""

    # 3) Prefer the full (visually-hidden) span; fallback to visible truncated span
    full = wrapper.find("span", class_=re.compile(r"\bvisually-hidden\b", re.I))
    if full:
        return normalize_html(full)

    visible = wrapper.find("span", attrs={"aria-hidden": "true"})
    if visible:
        return normalize_html(visible)

    # 4) Last resort: normalize whatever is inside the wrapper
    return normalize_html(wrapper)


# ===== Photo (optional local resolver; returns file:// if found else og:image/empty) =====

def get_photo_url(soup: BeautifulSoup, html_file: pathlib.Path) -> str:
    """
    Try to resolve a local profile photo path if present; else return og:image or empty.
    Strategy:
      1) <img alt contains person's name>
      2) og:image (remote)
      3) first image in top-card areas
    """
    name = get_name(soup)
    imgs = []

    for img in soup.find_all("img"):
        alt = txt(img.get("alt", ""))
        src = img.get("src", "") or img.get("data-delayed-url", "") or ""
        if src and name and name.lower() in alt.lower():
            imgs.append(src)

    ogimg = get_meta(soup, "og:image")
    if ogimg:
        imgs.append(ogimg)

    for sel in ['.pv-top-card img', '.top-card-layout img']:
        for el in soup.select(sel):
            src = el.get("src", "") or el.get("data-delayed-url", "") or ""
            if src:
                imgs.append(src)

    # Try to resolve relative paths into the local _files dir
    for src in imgs:
        s = (src or "").strip()
        if not s:
            continue
        if s.lower().startswith(("http://", "https://", "file://")):
            return s
        p = (html_file.parent / s).resolve()
        if p.exists():
            return f"file://{p}"
        for d in html_file.parent.iterdir():
            if d.is_dir() and d.name.endswith("_files"):
                p2 = (d / s).resolve()
                if p2.exists():
                    return f"file://{p2}"
    return ""

# ===== Generic section helpers (Experience/Education/Skills/Certs heuristics) =====

def extract_section_block(soup: BeautifulSoup, names: List[str]) -> str:
    # aria-label exact match first
    for w in names:
        sec = soup.find(attrs={"aria-label": re.compile(rf"\b{re.escape(w)}\b", re.I)})
        if sec:
            return txt(sec.get_text(" "))
    # headings fallback
    for h in soup.find_all(re.compile(r"^h[1-4]$", re.I)):
        if any(w.lower() in txt(h.get_text()).lower() for w in names):
            parent = h.parent
            if parent:
                return txt(parent.get_text(" "))
    return ""




from typing import List, Dict, Any
import re
from bs4 import BeautifulSoup, Comment

def extract_positions(block: str) -> List[Dict[str, Any]]:
    """
    Parse LinkedIn 'Experience' HTML into positions, including grouped roles.
    For each role we return:
      - title, company, location, startDate, endDate (None for Present), description
    """

    def _txt(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip())

    def _multiline(node) -> str:
        if not node:
            return ""
        for br in node.find_all("br"):
            br.replace_with("\n")
        for c in node.find_all(string=lambda t: isinstance(t, Comment)):
            c.extract()
        raw = node.get_text("\n", strip=True).replace("\xa0", " ")
        raw = re.sub(r"[ \t]+\n", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return "\n".join(line.rstrip() for line in raw.splitlines()).strip()

    def _prefer_text(node) -> str:
        if not node:
            return ""
        vh = node.find("span", class_=re.compile(r"\bvisually-hidden\b", re.I))
        if vh:
            return _txt(vh.get_text(" ", strip=True))
        ah = node.find("span", attrs={"aria-hidden": "true"})
        if ah:
            return _txt(ah.get_text(" ", strip=True))
        return _txt(node.get_text(" ", strip=True))

    DATE_PAT = re.compile(r"([A-Za-z]{3,9}\s+\d{4})\s*(?:-|to|–)\s*(Present|[A-Za-z]{3,9}\s+\d{4})", re.I)

    def _parse_date_range(s: str):
        s = _txt(s)
        m = DATE_PAT.search(s)
        if not m:
            return "", None
        start, end = m.group(1), m.group(2)
        if re.match(r"present", end, re.I):
            return start, None
        return start, end

    def _find_dates_near(scope):
        """
        Prefer dates inside the anchor; else search the surrounding list item / entity.
        """
        # 1) inside anchor captions
        cap = scope.select_one(".pvs-entity__caption-wrapper")
        if cap:
            sd, ed = _parse_date_range(_prefer_text(cap))
            if sd:
                return sd, ed
        for sp in scope.select("span.t-14.t-normal.t-black--light, span.t-14.t-normal"):
            sd, ed = _parse_date_range(_prefer_text(sp))
            if sd:
                return sd, ed

        # 2) try the list item wrapper
        li = scope.find_parent("li")
        if li:
            cap = li.select_one(".pvs-entity__caption-wrapper")
            if cap:
                sd, ed = _parse_date_range(_prefer_text(cap))
                if sd:
                    return sd, ed
            for sp in li.select("span.t-14.t-normal.t-black--light, span.t-14.t-normal"):
                sd, ed = _parse_date_range(_prefer_text(sp))
                if sd:
                    return sd, ed

        # 3) try the enclosing profile-component-entity
        ent = scope.find_parent('div', attrs={"data-view-name": "profile-component-entity"})
        if ent:
            cap = ent.select_one(".pvs-entity__caption-wrapper")
            if cap:
                sd, ed = _parse_date_range(_prefer_text(cap))
                if sd:
                    return sd, ed
            for sp in ent.select("span.t-14.t-normal.t-black--light, span.t-14.t-normal"):
                sd, ed = _parse_date_range(_prefer_text(sp))
                if sd:
                    return sd, ed

        return "", None

    def _company_from_logo(scope) -> str:
        img = scope.select_one('a[data-field="experience_company_logo"] img[alt]')
        if img and img.get("alt"):
            return _txt(re.sub(r"\s+logo$", "", img["alt"], flags=re.I))
        return ""

    def _nearest_company(scope) -> str:
        """
        Walk up through ancestor 'profile-component-entity' blocks and try to
        read the company name from a company header (logo row or header without dates).
        """
        ent = scope.find_parent('div', attrs={"data-view-name": "profile-component-entity"})
        while ent:
            # 1) explicit company logo block
            c = _company_from_logo(ent)
            if c:
                return c

            # 2) header with bold title and NO dates (typical company header)
            for a in ent.select("a.optional-action-target-wrapper"):
                bold = a.select_one(".hoverable-link-text.t-bold")
                if not bold:
                    continue
                # if this anchor has no date range within itself, it's likely the company header
                sd, _ = _find_dates_near(a)
                if not sd:
                    name = _prefer_text(bold)
                    if name:
                        return name

            # climb higher (some exports nest entities)
            ent = ent.find_parent('div', attrs={"data-view-name": "profile-component-entity"})
        return ""

    EMPLOYMENT_TERMS = ("Full-time","Part-time","Contract","Internship","Self-employed","Freelance","Temporary")

    items: List[Dict[str, Any]] = []
    if not block:
        return items

    soup = BeautifulSoup(block, "lxml")

    # Every clickable role (including grouped roles) is usually an optional-action-target-wrapper
    for a in soup.select("a.optional-action-target-wrapper"):
        href = a.get("href", "") or ""
        # ignore irrelevant overlays
        if any(k in href for k in ("skill-associations-details", "multiple-media-viewer")):
            continue

        # Title must be present
        title_node = a.select_one(".hoverable-link-text.t-bold")
        if not title_node:
            continue
        title = _prefer_text(title_node)
        if not title:
            continue

        # Need a date range somewhere near this role
        startDate, endDate = _find_dates_near(a)
        if not startDate:
            # If there is no date near this anchor it is very likely a company header; skip
            continue

        # Company: try line under the role first, else walk up to the nearest company header
        company = ""
        for sp in a.select("span.t-14.t-normal"):
            company = _prefer_text(sp)
            if company:
                break
        company = company.split("·", 1)[0].strip() if company else ""
        
        # Filter out date ranges and employment terms from company name
        if DATE_PAT.search(company) or any(term in company for term in EMPLOYMENT_TERMS) or re.search(r"\d+\s*(yrs?|mos?)", company, re.I):
            company = _nearest_company(a) or _company_from_logo(a) or ""

        # Location: any t-14 light span that looks like a place (not the date)
        location = ""
        for sp in a.select("span.t-14.t-normal.t-black--light"):
            t = _prefer_text(sp)
            if DATE_PAT.search(t):
                continue
            if "," in t or re.search(r"\b(India|Karnataka|Bengaluru|Bangalore|Hybrid|Remote|Area)\b", t, re.I):
                location = _txt(t.split("·", 1)[0])
                break
        if not location:
            li = a.find_parent("li")
            if li:
                for sp in li.select("span.t-14.t-normal.t-black--light"):
                    t = _prefer_text(sp)
                    if DATE_PAT.search(t):
                        continue
                    if "," in t or re.search(r"\b(India|Karnataka|Bengaluru|Bangalore|Hybrid|Remote|Area)\b", t, re.I):
                        location = _txt(t.split("·", 1)[0])
                        break

        # Description block
        description = ""
        li = a.find_parent("li")
        if li:
            wrap = li.find("div", class_=re.compile(r"inline-show-more-text", re.I))
            if wrap:
                vh = wrap.find("span", class_=re.compile(r"\bvisually-hidden\b", re.I))
                description = _multiline(vh or wrap.find("span", attrs={"aria-hidden": "true"}) or wrap)

        if title == company:
            items.append({
                "title": "",
                "company": company,
                "location": location,
                "startDate": startDate,
                "endDate": endDate,
                "description": description
            })
           
        if title != company:       
            items.append({
                "title": title,
                "company": company,
                "location": location,
                "startDate": startDate,
                "endDate": endDate,
                "description": description
            })

    # Deduplicate while preserving separate roles / date ranges
    unique, seen = [], set()
    for it in items:
        key = (
            it["title"].lower(),
            (it["company"] or "").lower(),
            (it["startDate"] or "").lower(),
            (it["endDate"] or "present").lower() if isinstance(it["endDate"], str) else "present",
        )
        if key not in seen:
            seen.add(key)
            unique.append(it)

    return unique





import re
from typing import Dict, List
from bs4 import BeautifulSoup

def _txt(s: str) -> str:
    import re
    return re.sub(r"\s+", " ", (s or "").strip())

def get_top_summary(soup: BeautifulSoup) -> Dict[str, List[str]]:
    """
    Extract the Current company and Education names from the top card,
    stripping LinkedIn's 'Click to skip to ... card' tail from aria-labels.
    """
    current_companies, top_educations = [], []
    seen_c, seen_e = set(), set()

    # Current company buttons have aria-label like:
    # 'Current company: ACME Corp. Click to skip to experience card'
    for btn in soup.select('button[aria-label*="Current company"]'):
        label = btn.get("aria-label", "")
        m = re.search(r"Current company:\s*(.+?)(?:\.\s*Click\b|$)", label, flags=re.I)
        val = _txt(m.group(1) if m else btn.get_text(" "))
        if val and val.lower() not in seen_c:
            seen_c.add(val.lower())
            current_companies.append(val)

    # Education buttons have aria-label like:
    # 'Education: University Name. Click to skip to education card'
    for btn in soup.select('button[aria-label^="Education:"]'):
        label = btn.get("aria-label", "")
        m = re.search(r"Education:\s*(.+?)(?:\.\s*Click\b|$)", label, flags=re.I)
        val = _txt(m.group(1) if m else btn.get_text(" "))
        if val and val.lower() not in seen_e:
            seen_e.add(val.lower())
            top_educations.append(val)

    # Fallbacks: sometimes the name is inside the small inline text next to the icon
    if not current_companies:
        for el in soup.select('ul li button .inline-show-more-text--is-collapsed'):
            t = _txt(el.get_text(" "))
            if t and len(t) < 120:
                current_companies.append(t)
                break
    if not top_educations:
        for el in soup.select('ul li button .inline-show-more-text--is-collapsed'):
            t = _txt(el.get_text(" "))
            if t and len(t) < 120:
                top_educations.append(t)
                break

    return {"currentCompanies": current_companies[:3], "topEducations": top_educations[:3]}





def extract_education(block: str) -> List[Dict[str, Any]]:
    """
    Parse a LinkedIn 'Education' HTML block into:
      [{school, degree, field, startDate, endDate}, ...]

    Notes for archived pages:
    - Some archives omit visible year ranges inside the Education rows.
      This function will still return entries without dates.
    - Prefers <span class="visually-hidden"> over aria-hidden for full text.
    - Tries to find dates anywhere within the entity; leaves them blank if absent.
    """
    if not block:
        return []

    import re
    from bs4 import BeautifulSoup, Comment

    def _txt(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip())

    def _prefer_text(node) -> str:
        if not node:
            return ""
        vh = node.find("span", class_=re.compile(r"\bvisually-hidden\b", re.I))
        if vh:
            return _txt(vh.get_text(" ", strip=True))
        ah = node.find("span", attrs={"aria-hidden": "true"})
        if ah:
            return _txt(ah.get_text(" ", strip=True))
        return _txt(node.get_text(" ", strip=True))

    def _parse_dates(text: str):
        m = re.search(r"(\d{4})\s*(?:-|to|–)\s*(Present|\d{4})", text, flags=re.I)
        if not m:
            return "", ""
        start, end = m.group(1), m.group(2)
        if re.match(r"present", end, re.I):
            return start, ""
        return start, end

    def _degree_and_field(raw: str):
        s = _txt(raw)
        # comma/pipe split first
        m = re.match(r"^(?P<deg>[^,|]+)[,|]\s*(?P<fld>.+)$", s)
        if m:
            return _txt(m.group("deg")), _txt(m.group("fld"))
        # fallback dash split
        m2 = re.match(r"^(?P<deg>.+?)\s*[–—-]\s*(?P<fld>[^–—-]{3,})$", s)
        if m2:
            return _txt(m2.group("deg")), _txt(m2.group("fld"))
        # no clear field; keep everything as degree
        return s, ""

    soup = BeautifulSoup(block, "lxml")

    # Remove empty comment nodes like <!---->
    for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()

    # If caller passed the whole page, narrow to the Education section if present
    scope = soup
    ed_anchor = soup.find(id="education")
    if ed_anchor:
        scope = ed_anchor.find_parent("section") or ed_anchor.parent

    items: List[Dict[str, Any]] = []

    # Each education entry is usually one 'profile-component-entity'
    for ent in scope.select('div[data-view-name="profile-component-entity"]'):
        # main anchor that holds school + degree
        a = ent.select_one("a.optional-action-target-wrapper.display-flex.flex-column.full-width") \
            or ent.select_one("a.optional-action-target-wrapper")
        if not a:
            continue

        school_node = a.select_one(".hoverable-link-text.t-bold")
        school = _prefer_text(school_node)
        if not school:
            continue

        # Degree (+ optional field) typically sits in the first t-14.t-normal span within the anchor
        deg_node = a.select_one("span.t-14.t-normal")
        deg_field_text = _prefer_text(deg_node) if deg_node else ""
        degree, field = _degree_and_field(deg_field_text) if deg_field_text else ("", "")

        # Dates may live in various places; search the whole entity
        start, end = "", ""
        cap = ent.select_one(".pvs-entity__caption-wrapper")
        if cap:
            start, end = _parse_dates(_prefer_text(cap))
        if not (start or end):
            for sp in ent.select("span.t-14.t-normal.t-black--light, span.t-14.t-normal"):
                st, en = _parse_dates(_prefer_text(sp))
                if st or en:
                    start, end = st, en
                    break

        items.append({
            "school": school,
            "degree": degree,
            "field": field,
            "startDate": start or "",
            "endDate": end or ""
        })

    # Deduplicate by (school, degree, startDate)
    unique, seen = [], set()
    for it in items:
        key = (it["school"].lower(), (it["degree"] or "").lower(), (it["startDate"] or ""))
        if key not in seen:
            seen.add(key)
            unique.append(it)

    return unique[:20]







def extract_skills(block: str) -> List[str]:
    """
    Extract LinkedIn skills from the Skills section HTML you shared.
    Works even when the text is split across <span aria-hidden="true"> and <span class="visually-hidden">.

    Strategy (scoped to the <section> that contains id="skills" when available):
      1) Grab anchors with data-field="skill_card_skill_topic" and read the
         nested ".hoverable-link-text.t-bold" text (prefer .visually-hidden).
      2) Also read any ".hoverable-link-text.t-bold" inside the skills section
         (covers minor markup variations).
      3) Fallback to common legacy selectors.
      4) Deduplicate & filter UI noise like "Show all 71 skills".
    """
    if not block:
        return []

    import re
    from bs4 import BeautifulSoup, Comment

    def _txt(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip())

    def _prefer_text(node) -> str:
        """Prefer full text in visually-hidden; fallback to aria-hidden/visible text."""
        if not node:
            return ""
        vh = node.find("span", class_=re.compile(r"\bvisually-hidden\b", re.I))
        if vh:
            return _txt(vh.get_text(" ", strip=True))
        ah = node.find("span", attrs={"aria-hidden": "true"})
        if ah:
            return _txt(ah.get_text(" ", strip=True))
        return _txt(node.get_text(" ", strip=True))

    soup = BeautifulSoup(block, "lxml")

    # Strip empty comments like <!---->
    for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()

    # Narrow scope to the real Skills section if present
    scope = soup
    anchor = soup.find(id="skills")
    if anchor:
        sec = anchor.find_parent("section")
        if sec:
            scope = sec

    skills, seen = [], set()

    def add(val: str):
        s = _txt(val)
        if not s:
            return
        if len(s) > 64:  # overly long phrases are unlikely to be skill names
            return
        # Filter UI noise
        if re.fullmatch(r"(About|Experience|Education|Skills|Certifications)", s, re.I):
            return
        if re.search(r"\b(Show all|see more|endorse|recommend|connections?)\b", s, re.I):
            return
        if re.search(r"\b\d+\s+skills?\b", s, re.I):  # e.g. "Show all 71 skills"
            return
        low = s.lower()
        if low not in seen:
            seen.add(low)
            skills.append(s)

    # 1) Primary: modern skill cards (as in your snippet)
    for a in scope.select('a.optional-action-target-wrapper[data-field="skill_card_skill_topic"]'):
        bold = a.select_one(".hoverable-link-text.t-bold")
        if bold:
            add(_prefer_text(bold))

    # 2) Also accept any bold skill chips inside the skills section
    #    (covers minor DOM variations where the anchor selector changes)
    for bold in scope.select(".hoverable-link-text.t-bold"):
        # Avoid double-adding items already captured from step 1
        add(_prefer_text(bold))

    # 3) Legacy/other selectors sometimes seen in exports
    for el in scope.select("span.pv-skill-category-entity__name-text, span.pv-skill-category-entity__name, .artdeco-pill .artdeco-pill__text, [data-test-skill-name]"):
        add(_prefer_text(el))
    
    # 4) Additional fallback selectors for skills
    for el in scope.select("span[class*='skill'], .pv-skill-category-entity__name, .pv-skill-category-entity__name-text, .artdeco-pill__text"):
        add(_prefer_text(el))
    
    # 5) Look for any text that might be skills in the skills section
    for el in scope.select("span, div, a"):
        text = _prefer_text(el)
        if text and len(text) < 50 and not re.search(r"\b(show|more|all|skills?|endorse|recommend)\b", text, re.I):
            # Check if it looks like a skill (not too long, not a UI element)
            if not re.search(r"\b(about|experience|education|certifications?|patents?|services?)\b", text, re.I):
                add(text)

    return skills[:100]



from typing import List
import re
from bs4 import BeautifulSoup, Comment

def extract_certifications(soup: BeautifulSoup) -> List[str]:
    """
    Extract certification titles from the 'Licenses & certifications' section.

    Targets the markup you shared (id='licenses_and_certifications') and the
    generic "Licenses & certifications" header. Prefers the bold title text,
    handles items like "Generative AI - Certifications (5)" by stripping the
    trailing counter, and deduplicates case-insensitively.
    """
    if not soup:
        return []

    def _txt(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip())

    def _prefer_text(node) -> str:
        if not node:
            return ""
        vh = node.find("span", class_=re.compile(r"\bvisually-hidden\b", re.I))
        if vh:
            return _txt(vh.get_text(" ", strip=True))
        ah = node.find("span", attrs={"aria-hidden": "true"})
        if ah:
            return _txt(ah.get_text(" ", strip=True))
        return _txt(node.get_text(" ", strip=True))

    # Locate the section
    section = None
    anchor = soup.find(id="licenses_and_certifications")
    if anchor:
        section = anchor.find_parent("section")
    if not section:
        for h2 in soup.select("h2.pvs-header__title"):
            label = " ".join(h2.stripped_strings).lower()
            if "license" in label and "certification" in label:
                section = h2.find_parent("section")
                break
    if not section:
        section = soup.find(attrs={"aria-label": re.compile(r"licenses?\s*&?\s*certifications?", re.I)})
    if not section:
        return []

    # Remove empty comments
    for c in section.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()

    titles, seen = [], set()

    # Each card lives under a profile-component entity
    for entity in section.select('div[data-view-name="profile-component-entity"]'):
        # Prefer the bold title (can be in <a> or a plain div)
        title_node = entity.select_one(".hoverable-link-text.t-bold, .t-bold")
        title = _prefer_text(title_node) if title_node else ""
        if not title:
            continue

        # Strip trailing " - Certifications (N)" or similar variants
        title = re.sub(r"\s*[-–—]\s*Certifications?\s*\(\d+\)\s*$", "", title, flags=re.I).strip()
        # Also trim any lingering "Show credential" noise just in case
        title = re.sub(r"\bShow credential\b", "", title, flags=re.I).strip()

        low = title.lower()
        if low and low not in seen:
            seen.add(low)
            titles.append(title)

    return titles[:50]



from typing import Dict, List
import re
from bs4 import BeautifulSoup, Comment

def extract_Recommendations(soup: BeautifulSoup) -> Dict[str, List[dict]]:
    """
    Extract LinkedIn Recommendations from the page soup, split into 'received' and 'given'.

    Return shape:
    {
      "received": [
        {
          "name": "...",
          "headline": "...",
          "dateLine": "December 21, 2024, Ashish managed Sudarshana directly",
          "text": "Full recommendation text...",
          "profileUrl": "https://www.linkedin.com/in/...."
        },
        ...
      ],
      "given": [ ...same fields... ]
    }
    """
    def _txt(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip())

    def _prefer_text(node) -> str:
        if not node:
            return ""
        vh = node.find("span", class_=re.compile(r"\bvisually-hidden\b", re.I))
        if vh:
            return _txt(vh.get_text(" ", strip=True))
        ah = node.find("span", attrs={"aria-hidden": "true"})
        if ah:
            return _txt(ah.get_text(" ", strip=True))
        return _txt(node.get_text(" ", strip=True))

    def _multiline(node) -> str:
        if not node:
            return ""
        for br in node.find_all("br"):
            br.replace_with("\n")
        for c in node.find_all(string=lambda t: isinstance(t, Comment)):
            c.extract()
        raw = node.get_text("\n", strip=True).replace("\xa0", " ")
        raw = re.sub(r"[ \t]+\n", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return "\n".join(line.rstrip() for line in raw.splitlines()).strip()

    def _find_reco_text(scope) -> str:
        # Find the expanded recommendation text block inside this list item
        wrap = scope.find("div", class_=re.compile(r"inline-show-more-text", re.I))
        if not wrap:
            return ""
        full = wrap.find("span", class_=re.compile(r"\bvisually-hidden\b", re.I))
        if full:
            return _multiline(full)
        vis = wrap.find("span", attrs={"aria-hidden": "true"})
        if vis:
            return _multiline(vis)
        return _multiline(wrap)

    def _panel_kind(panel) -> str:
        """Decide if this tabpanel is 'received' or 'given'."""
        # 1) Look for "Show all ... received/given" footer text
        footer_text = panel.get_text(" ", strip=True).lower()
        if re.search(r"\breceived\b", footer_text):
            return "received"
        if re.search(r"\bgiven\b", footer_text):
            return "given"
        # 2) Use the aria-labelledby -> button text if available
        lab = panel.get("aria-labelledby")
        if lab:
            btn = panel.find_parent().find(id=lab)
            if btn:
                btxt = _txt(btn.get_text(" "))
                if re.search(r"\breceived\b", btxt, re.I):
                    return "received"
                if re.search(r"\bgiven\b", btxt, re.I):
                    return "given"
        # 3) Fallback by position: first = received, others = given
        siblings = list(panel.parent.select("[role='tabpanel']"))
        if siblings and siblings[0] is panel:
            return "received"
        return "given"

    def _section_root():
        # Prefer the section anchored by id="recommendations"
        sec_anchor = soup.find(id=re.compile(r"^recommendations$", re.I))
        if sec_anchor:
            sec = sec_anchor.find_parent("section")
            if sec:
                return sec
        # Fallback: find by heading text
        for h2 in soup.select("h2.pvs-header__title"):
            if "recommendations" in _txt(h2.get_text()).lower():
                sec = h2.find_parent("section")
                if sec:
                    return sec
        return None

    root = _section_root()
    if not root:
        return {"received": [], "given": []}

    out = {"received": [], "given": []}

    # Iterate tabpanels (Received / Given)
    panels = root.select("[role='tabpanel']") or [root]  # fallback if no tabs found
    for panel in panels:
        kind = _panel_kind(panel)

        # Each recommendation card lives under a profile-component-entity inside list items
        for ent in panel.select('div[data-view-name="profile-component-entity"]'):
            li = ent.find_parent("li") or ent

            # Person anchor with bold name
            name = headline = profileUrl = ""
            person_anchor = None
            for a in ent.select("a.optional-action-target-wrapper"):
                if a.select_one(".hoverable-link-text.t-bold"):
                    person_anchor = a
                    break
            if person_anchor:
                name_node = person_anchor.select_one(".hoverable-link-text.t-bold")
                name = _prefer_text(name_node)
                profileUrl = person_anchor.get("href", "") or profileUrl
                # Headline sits right under the name anchor as span.t-14.t-normal
                head_node = person_anchor.select_one("span.t-14.t-normal")
                if not head_node:
                    # sometimes sibling spans carry the headline
                    head_node = ent.select_one("span.t-14.t-normal")
                headline = _prefer_text(head_node)

            # Date/relationship line
            dateLine = ""
            cap = ent.select_one(".pvs-entity__caption-wrapper")
            if cap:
                dateLine = _prefer_text(cap)

            # Recommendation text
            text = _find_reco_text(li)

            # Skip empty shells
            if not (name or text):
                continue

            out[kind].append({
                "name": name,
                "headline": headline,
                "dateLine": dateLine,
                "text": text,
                "profileUrl": profileUrl
            })

    return out






import re
from typing import List
from bs4 import BeautifulSoup, Comment

def extract_services(soup: BeautifulSoup) -> List[str]:
    """
    Extract a flat list of service names from the 'Services' section.

    - Locates the section via id="services" or the 'Services' H2
    - Prefers <span class="visually-hidden"> (full text), falls back to aria-hidden
    - Splits on bullets/newlines into individual services
    - Deduplicates (case-insensitive) and filters UI noise
    """

    def _txt(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip())

    def _prefer_text(node) -> str:
        if not node:
            return ""
        vh = node.find("span", class_=re.compile(r"\bvisually-hidden\b", re.I))
        if vh:
            return _txt(vh.get_text(" ", strip=True))
        ah = node.find("span", attrs={"aria-hidden": "true"})
        if ah:
            return _txt(ah.get_text(" ", strip=True))
        return _txt(node.get_text(" ", strip=True))

    # 1) Find the Services section root
    section = None
    anchor = soup.find(id=re.compile(r"^services$", re.I))
    if anchor:
        section = anchor.find_parent("section")
    if not section:
        for h2 in soup.select("h2.pvs-header__title"):
            if "services" in _txt(h2.get_text(" ")).lower():
                section = h2.find_parent("section")
                break
    if not section:
        return []

    # 2) Clean out empty comments like <!---->
    for c in section.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()

    # 3) Collect raw text chunks that list services (bold/inline-show-more areas)
    raw_chunks: List[str] = []

    # Primary: the inline show-more wrapper in your snippet
    for wrap in section.select(".inline-show-more-text--is-collapsed, .inline-show-more-text--is-expanded"):
        raw = _prefer_text(wrap)
        if raw:
            raw_chunks.append(raw)

    # Fallbacks: any bold service lines inside the section (e.g., <strong>…</strong>)
    for strong in section.select("strong"):
        raw = _txt(strong.get_text(" ", strip=True))
        if raw:
            raw_chunks.append(raw)

    if not raw_chunks:
        # Last resort: grab the section’s visible text and try to split
        raw = _prefer_text(section)
        if raw:
            raw_chunks.append(raw)

    if not raw_chunks:
        return []

    # 4) Split into individual services on bullets/newlines (avoid commas to keep names intact)
    SEP = re.compile(r"[•\u2022·\n\r]+")
    services, seen = [], set()

    def add(s: str):
        val = _txt(s)
        if not val:
            return
        # Filter obvious UI noise
        if re.search(r"\b(show all services|edit services)\b", val, re.I):
            return
        if re.fullmatch(r"(services|about|experience|education|skills|certifications)", val, re.I):
            return
        # Length sanity (names are short phrases)
        if len(val) > 80:
            return
        low = val.lower()
        if low not in seen:
            seen.add(low)
            services.append(val)

    for chunk in raw_chunks:
        # Some exports include everything in one bold line separated by bullets
        parts = [p for p in SEP.split(chunk) if p is not None]
        for p in parts:
            add(p)

    return services[:50]





import re
from typing import List, Dict
from bs4 import BeautifulSoup, Comment

def extract_patents(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """
    Extract patents from the 'Patents' section.

    Returns a list of dicts:
    {
      "title": "...",
      "office": "US",
      "number": "5974463",
      "kind": "A",
      "status": "Issued",         # or Filed / Granted / Published (best-effort)
      "date": "Oct 26, 1999",
      "url": "http://... (See patent)",
      "summary": "..."
    }
    """

    def _txt(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip())

    def _prefer_text(node) -> str:
        if not node:
            return ""
        vh = node.find("span", class_=re.compile(r"\bvisually-hidden\b", re.I))
        if vh:
            return _txt(vh.get_text(" ", strip=True))
        ah = node.find("span", attrs={"aria-hidden": "true"})
        if ah:
            return _txt(ah.get_text(" ", strip=True))
        return _txt(node.get_text(" ", strip=True))

    def _multiline(node) -> str:
        if not node:
            return ""
        for br in node.find_all("br"):
            br.replace_with("\n")
        for c in node.find_all(string=lambda t: isinstance(t, Comment)):
            c.extract()
        raw = node.get_text("\n", strip=True).replace("\xa0", " ")
        raw = re.sub(r"[ \t]+\n", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return "\n".join(line.rstrip() for line in raw.splitlines()).strip()

    # ---- locate section root
    section = None
    anchor = soup.find(id=re.compile(r"^patents$", re.I))
    if anchor:
        section = anchor.find_parent("section")
    if not section:
        for h2 in soup.select("h2.pvs-header__title"):
            if "patents" in _txt(h2.get_text(" ")).lower():
                section = h2.find_parent("section")
                break
    if not section:
        return []

    # strip empty comments
    for c in section.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()

    items: List[Dict[str, str]] = []
    seen = set()

    # Each card
    for ent in section.select('div[data-view-name="profile-component-entity"]'):
        # Title (bold)
        title_node = ent.select_one(".hoverable-link-text.t-bold, .t-bold")
        title = _prefer_text(title_node)
        if not title:
            continue

        # Meta line like: "US US 5974463 A · Issued Oct 26, 1999"
        meta = ""
        # Prefer the first t-14 t-normal directly under the same block
        meta_node = None
        for cand in ent.select("span.t-14.t-normal"):
            text = _prefer_text(cand)
            if re.search(r"\b(Issued|Filed|Granted|Published)\b", text, re.I) or re.search(r"\b[A-Z]{2}\b.*\d", text):
                meta_node = cand
                break
        if meta_node:
            meta = _prefer_text(meta_node)

        # Parse office/number/kind + status/date from meta
        office = number = kind = status = date = ""
        if meta:
            # Split at the middle dot / bullet if present
            parts = re.split(r"\s*[·•]\s*", meta, maxsplit=1)
            left = parts[0]
            right = parts[1] if len(parts) > 1 else ""

            # LEFT: e.g., "US US 5974463 A" or "US US 20100315200 A1"
            toks = left.split()
            # collect office codes until first token with a digit
            office_tokens, rest = [], []
            hit_digit = False
            for t in toks:
                if not hit_digit and not re.search(r"\d", t):
                    # likely "US" repeated; keep unique
                    if t.upper() not in (ot.upper() for ot in office_tokens):
                        office_tokens.append(t)
                else:
                    hit_digit = True
                    rest.append(t)
            office = " ".join(office_tokens).strip()

            # number + kind: last token may be kind (e.g., A, A1, B1)
            if rest:
                # If last token looks like kind code, peel it off
                if re.fullmatch(r"[A-Z]\d?", rest[-1], re.I) or re.fullmatch(r"[A-Z]\d?", rest[-1].replace(".", "")):
                    kind = rest[-1].upper()
                    rest = rest[:-1]
                number = " ".join(rest).strip()

            # RIGHT: e.g., "Issued Oct 26, 1999"
            if right:
                m = re.search(r"\b(Issued|Filed|Granted|Published)\b\s+([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})", right, re.I)
                if m:
                    status = m.group(1).title()
                    date = m.group(2)

            # Fallback if nothing parsed from right side
            if not status:
                m2 = re.search(r"\b(Issued|Filed|Granted|Published)\b", meta, re.I)
                if m2:
                    status = m2.group(1).title()
            if not date:
                m3 = re.search(r"([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})", meta)
                if m3:
                    date = m3.group(1)

        # URL: "See patent" button
        url = ""
        for a in ent.select("a[href]"):
            txt = _txt(a.get_text(" ", strip=True)).lower()
            aria = (a.get("aria-label") or "").lower()
            if "see patent" in txt or "see patent" in aria:
                url = a["href"].strip()
                break

        # Summary/abstract (inline-show-more)
        summary = ""
        wrap = ent.find("div", class_=re.compile(r"inline-show-more-text", re.I))
        if wrap:
            full = wrap.find("span", class_=re.compile(r"\bvisually-hidden\b", re.I))
            if full:
                summary = _multiline(full)
            else:
                vis = wrap.find("span", attrs={"aria-hidden": "true"})
                if vis:
                    summary = _multiline(vis)
                else:
                    summary = _multiline(wrap)

        record = {
            "title": title,
            "office": office,
            "number": number,
            "kind": kind,
            "status": status,
            "date": date,
            "url": url,
            "summary": summary,
        }

        # Dedup by (title, number, date) to avoid doubles
        key = (record["title"].lower(), record["number"].lower(), record["date"].lower())
        if key not in seen:
            seen.add(key)
            items.append(record)

    # Filter out footer/UI noise if it slipped through
    filtered = []
    for it in items:
        joined = " ".join(it.values()).lower()
        if re.search(r"\bshow all \d+ patents\b", joined):
            continue
        filtered.append(it)

    return filtered[:50]


# ---------- ADD EMAIL EXTRACTOR RIGHT HERE ----------
def extract_emails(soup: BeautifulSoup) -> list[str]:
    import re
    emails = set()

    # 1) Direct mailto links
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().startswith("mailto:"):
            emails.add(href[7:].split("?")[0].strip())

    # 2) Emails in visible or hidden text
    text = soup.get_text(" ", strip=True)
    found = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    for e in found:
        emails.add(e.strip())

    return sorted(emails)










# -------------------- main parse --------------------

def parse_profile_html(html_path: pathlib.Path) -> Optional[Dict[str, Any]]:
    text = html_path.read_text(encoding="utf-8", errors="ignore")
    if "linkedin.com" not in text.lower():
        return None

    soup = BeautifulSoup(text, "lxml")

    profile_url = get_profile_url(soup)

    exp_section_html = str(soup.find(id="experience").find_parent("section")) if soup.find(id="experience") else ""
    positions = extract_positions(exp_section_html or str(soup))

    # Grab the dedicated Education section HTML if present, else fall back
    edu_section_html = str(soup.find(id="education").find_parent("section")) if soup.find(id="education") else ""
    education = extract_education(edu_section_html or extract_section_block(soup, ["Education"]))

    # get the Skills section HTML first, then parse it
    sec = soup.find(id="skills")
    skills_html = str(sec.find_parent("section")) if sec else ""
    skills = extract_skills(skills_html)

    recommendations = extract_Recommendations(soup)

    services = extract_services(soup)
    
    patents = extract_patents(soup)


    data = {
        "fullName": get_name(soup),                # UNCHANGED
        "headline": get_headline(soup),            # UNCHANGED
        "location": get_location(soup),
        "profileUrl": profile_url,
        "photoUrl": get_photo_url(soup, html_path),
        "about": get_about(soup),
        "designation": next((pos["title"] for pos in positions if pos["title"]), ""),
        "positions": positions,
        "educations": education,
        "services": services,
        "skills": skills,
        "certifications": extract_certifications(soup),
        "websites": get_websites(soup),
        "patents": patents,
        "recommendations": recommendations,
        "emails": extract_emails(soup),

        
    }



    # Accept only if at least name or URL to avoid noise
    if not (data["fullName"] or data["profileUrl"]):
        return None
    return data

def main(input_path: str, out_path: str = None) -> None:
    input_path_obj = pathlib.Path(input_path)
    if not input_path_obj.exists():
        print(f"ERROR: Input path not found: {input_path_obj}")
        sys.exit(1)

    # Determine if input is a zip file or a folder
    if input_path_obj.is_file() and input_path_obj.suffix.lower() == '.zip':
        # Handle zip file
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="linkedin_archive_"))
        extract_dir = tmp / "unzipped"
        extract_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(input_path_obj, "r") as z:
            z.extractall(extract_dir)
        
        # gather html-like files from extracted zip
        html_files: List[pathlib.Path] = []
        for ext in ("*.html", "*.htm", "*.mhtml"):
            html_files.extend(extract_dir.rglob(ext))
    else:
        # Handle regular folder
        extract_dir = input_path_obj
        
        # gather html-like files from folder
        html_files: List[pathlib.Path] = []
        for ext in ("*.html", "*.htm", "*.mhtml"):
            html_files.extend(extract_dir.rglob(ext))

    # Create output directory
    output_dir = pathlib.Path("output")
    output_dir.mkdir(exist_ok=True)
    
    # Create timestamp for this batch
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    processed_count = 0
    
    for f in html_files:
        try:
            # Skip files that are likely not LinkedIn profiles
            if any(skip in f.name.lower() for skip in ['recaptcha', 'adobe', 'image', 'open forum', 'work with us']):
                continue
                
            rec = parse_profile_html(f)
            if rec and rec.get("fullName") and rec.get("fullName") not in ['reCAPTCHA', 'Open Forum', 'Work With Us', 'Image By Linkedin', 'Adobe AudienceManager']:
                processed_count += 1
                
                # Create individual file for each profile
                profile_name = rec.get("fullName", "Unknown").replace(" ", "_").replace("/", "_").replace("\\", "_")
                safe_name = "".join(c for c in profile_name if c.isalnum() or c in ('_', '-')).strip('_')
                
                if not safe_name or safe_name == "Unknown":
                    safe_name = f"profile_{processed_count}"
                
                individual_file = output_dir / f"{safe_name}_{timestamp}.json"
                individual_file.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f" Parsed: {rec.get('fullName', 'Unknown')} → {individual_file.name}")
            else:
                print(f" Skipped: {f.name} (not a valid LinkedIn profile)")
                
        except Exception as e:
            print(f" Error processing {f.name}: {str(e)}")
            continue



    # ----------------------------------------
    # DELETE ALL FILES IN saved_profiles FOLDER
    # ----------------------------------------
    saved_profiles_dir = pathlib.Path("saved_profiles")

    if saved_profiles_dir.exists() and saved_profiles_dir.is_dir():
        deleted_count = 0
        import shutil

        for item in saved_profiles_dir.iterdir():
            try:
                if item.is_file():
                    item.unlink()
                    deleted_count += 1
                elif item.is_dir():
                    shutil.rmtree(item)
                    deleted_count += 1
            except Exception as e:
                print(f"⚠️ Could not delete {item}: {e}")

        print(f"\n  Cleaned saved_profiles folder — deleted {deleted_count} items.")
    else:
        print("\nsaved_profiles folder not found — skipping cleanup.")

    # Print summary
    if processed_count > 0:
        print(f"\n All files saved in: {output_dir.absolute()}")
        print(f"Total profiles parsed: {processed_count}")
    else:
        print(" No profiles were successfully parsed.")




if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python parse_linkedin_02.py <input_path>")
        print("  input_path: Path to LinkedIn archive (zip file) or folder containing HTML files")
        print("")
        print("Output:")
        print("  - Individual JSON files for each profile in 'output/' folder")
        print("  - Files are named with profile names and timestamps")
        print("")
        print("Examples:")
        print("  python parse_linkedin_02.py input.zip")
        print("  python parse_linkedin_02.py ./linkedin_folder")
        print("  python parse_linkedin_02.py \"C:\\Users\\Name\\LinkedIn Data\"")
        sys.exit(1)
    main(sys.argv[1], None)


    #python parse_linkedin_02.py input_1
