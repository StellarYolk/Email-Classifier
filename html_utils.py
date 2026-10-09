from bs4 import BeautifulSoup

# Hard cap on cleaned body length fed to the model. This isn't about
# correctness — it's about speed and cost. A newsletter or marketing email
# can have thousands of words of footer/legal text after cleaning; the
# model needs maybe the first few hundred words to classify it correctly.
# On constrained hardware (GTX 1650), every extra token here is latency
# you pay 20 times per batch. Tune this once you see real timings.
MAX_BODY_CHARS = 2000


def clean_html_body(raw_html: str) -> str:
    """
    Converts an HTML email body into plain, readable text suitable for the
    classification prompt. Used ONLY when an email has no text/plain part
    to fall back on (that preference is handled at the Gmail-fetch layer,
    not here).
    """
    soup = BeautifulSoup(raw_html, "html.parser")

    # <script> and <style> tags contain no human-readable content, but
    # BeautifulSoup's get_text() would otherwise include their raw contents
    # (JS code, CSS rules) as if it were part of the email's text. Must
    # strip these BEFORE calling get_text(), not after.
    for tag in soup(["script", "style"]):
        tag.decompose()

    # separator=" " prevents words from different block-level elements
    # (e.g. a <div> next to another <div>) from being smashed together
    # with no space, which get_text() does by default and which produces
    # garbled, misleading text for the model to read.
    text = soup.get_text(separator=" ")

    # HTML emails are notorious for excessive whitespace from nested
    # tables/divs used for layout. Collapsing runs of whitespace down to
    # single spaces keeps token count honest — otherwise you're paying
    # for whitespace tokens that carry no signal.
    text = " ".join(text.split())

    if len(text) > MAX_BODY_CHARS:
        text = text[:MAX_BODY_CHARS] + " [truncated]"

    return text


if __name__ == "__main__":
    sample_html = """
    <html>
      <head><style>.promo { color: red; }</style></head>
      <body>
        <script>trackOpen('abc123');</script>
        <div style="padding:20px">
          <table><tr><td>
            <h1>50% OFF Everything!</h1>
            <p>Hey there, your favorite items are     on sale.</p>
          </td></tr></table>
        </div>
        <img src="tracker.gif" width="1" height="1">
      </body>
    </html>
    """
    print(repr(clean_html_body(sample_html)))