#!/usr/bin/env python3
"""Job alert for Jayanta Tamuli.

Fetches new jobs from free public feeds, keeps only ones that match your CV
keywords, and sends a phone/desktop notification for every NEW post.

Notification options (set as environment variables / GitHub secrets):
  NTFY_TOPIC          free push notifications via the ntfy app (easiest)
  TELEGRAM_BOT_TOKEN  and TELEGRAM_CHAT_ID   (optional)

Run:  python job_alert.py
"""
import json, os, re, sys, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

SEEN_FILE = Path(__file__).with_name("seen.json")

# Titles must contain one of these words (from your CV).
MATCH = ["wordpress", "woocommerce", "php", "laravel", "shopify", "elementor",
         "divi", "react", "front end", "frontend", "front-end", "full stack", "fullstack", "web developer"]
# Skip jobs clearly too senior for 2+ years experience.
SKIP = ["senior", "sr.", "lead", "principal", "architect", "manager", "head of", "director", "staff "]

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 job-alert"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def remotive():
    out = []
    for term in ["wordpress", "php", "laravel", "shopify", "react"]:
        data = json.loads(get("https://remotive.com/api/remote-jobs?search=" + term))
        for j in data.get("jobs", []):
            out.append(dict(id="remotive-%s" % j["id"], title=j["title"], company=j["company_name"],
                            url=j["url"], where=j.get("candidate_required_location", "Remote"), src="Remotive"))
    return out

def remoteok():
    data = json.loads(get("https://remoteok.com/api"))
    return [dict(id="remoteok-%s" % j["id"], title=j.get("position", ""), company=j.get("company", ""),
                 url=j.get("url", ""), where=j.get("location") or "Remote", src="RemoteOK")
            for j in data if isinstance(j, dict) and j.get("id")]

def wwr():
    out = []
    xml = get("https://weworkremotely.com/categories/remote-programming-jobs.rss")
    for it in ET.fromstring(xml).iter("item"):
        t = it.findtext("title", "")
        company, _, title = t.partition(": ")
        out.append(dict(id="wwr-" + it.findtext("guid", t), title=title or t, company=company,
                        url=it.findtext("link", ""), where="Remote", src="WeWorkRemotely"))
    return out

# Add your own feeds here. Many sites (LinkedIn, Naukri, Indeed) block bots, so
# use their built-in "job alert" email for those and keep this script for the rest.
SOURCES = [remotive, remoteok, wwr]

def matches(job):
    t = job["title"].lower()
    return any(k in t for k in MATCH) and not any(k in t for k in SKIP)

def notify(job):
    title = "New job: %s" % job["title"]
    body = "%s | %s | %s\n%s" % (job["company"], job["where"], job["src"], job["url"])
    topic = os.getenv("NTFY_TOPIC")
    if topic:
        req = urllib.request.Request("https://ntfy.sh/" + topic, data=body.encode(),
                                     headers={"Title": title, "Click": job["url"], "Tags": "briefcase"})
        urllib.request.urlopen(req, timeout=30)
    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if tok and chat:
        q = urllib.parse.urlencode({"chat_id": chat, "text": title + "\n" + body})
        urllib.request.urlopen("https://api.telegram.org/bot%s/sendMessage?%s" % (tok, q), timeout=30)
    if not topic and not tok:
        print(title, "-", body)

def main():
    seen = set(json.loads(SEEN_FILE.read_text())) if SEEN_FILE.exists() else set()
    first_run = not SEEN_FILE.exists()
    new = []
    for src in SOURCES:
        try:
            for job in src():
                if job["id"] not in seen:
                    seen.add(job["id"])
                    if matches(job):
                        new.append(job)
        except Exception as e:
            print("source failed:", src.__name__, e, file=sys.stderr)
    if first_run:
        print("First run: saved %d existing jobs, no alerts sent." % len(seen))
    else:
        for job in new[:30]:
            notify(job)
        print("Sent %d alerts." % len(new[:30]))
    SEEN_FILE.write_text(json.dumps(sorted(seen)))

if __name__ == "__main__":
    main()
