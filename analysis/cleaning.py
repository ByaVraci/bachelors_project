import re

# fenced blocks must be removed before inline backticks,
# and templates before generic markdown, or the regexes interfere.

FENCED_CODE   = re.compile(r"```.*?```", re.DOTALL)   # ```python ... ```
INLINE_CODE   = re.compile(r"`[^`]*`")                # `variable`
CHECKBOX_LINE = re.compile(r"^\s*[-*]\s*\[[ xX]\].*$", re.MULTILINE)
ISSUE_LINK    = re.compile(r"^\s*Issue link:.*$", re.MULTILINE)
HTML_COMMENT  = re.compile(r"<!--.*?-->", re.DOTALL)  # GitHub PR templates
MENTION_REF   = re.compile(r"[@#]\w[\w-]*")           # @user, #1234
URL           = re.compile(r"https?://\S+")
MD_HEADER     = re.compile(r"^\s{0,3}#{1,6}\s.*$", re.MULTILINE)
MD_EMPHASIS   = re.compile(r"[*_~]{1,3}")             # **bold** _italic_
HR_RULE       = re.compile(r"^\s*-{3,}\s*$", re.MULTILINE)
MULTISPACE    = re.compile(r"\s+")

def clean_for_linguistics(text: str) -> str:
    """
    Strips everything that is not natural prose, so linguistic
    metrics measure human language rather than code or boilerplate.
    Returns '' if nothing prose-like remains.
    """
    if not text:
        return ""
    t = str(text)
    t = HTML_COMMENT.sub(" ", t)
    t = FENCED_CODE.sub(" ", t)      # removes ```suggestion``` too
    t = CHECKBOX_LINE.sub(" ", t)    # PR template checklists
    t = ISSUE_LINK.sub(" ", t)
    t = MD_HEADER.sub(" ", t)
    t = HR_RULE.sub(" ", t)
    t = INLINE_CODE.sub(" ", t)
    t = URL.sub(" ", t)
    t = MENTION_REF.sub(" ", t)      # after URL so URLs aren't half-eaten
    t = MD_EMPHASIS.sub("", t)
    t = MULTISPACE.sub(" ", t).strip()
    return t

def is_prose(text: str) -> bool:
    """A comment is prose if cleaning leaves at least a few real words."""
    cleaned = clean_for_linguistics(text)
    return len(cleaned.split()) >= 1