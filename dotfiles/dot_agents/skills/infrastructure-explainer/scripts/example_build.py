"""A small worked example and smoke test: two panels for a made-up "orders" service.

    python3 aws_icons.py --zip Asset-Package.zip --out icons/ <the file names in ICONS below>
    python3 example_build.py icons/ example.html && python3 render_cards.py example.html render/
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diagram_kit import Kit, page  # noqa: E402

ICONS = {
    "eks": "Arch_Amazon-Elastic-Kubernetes-Service_48.svg",
    "role": "Res_AWS-Identity-Access-Management_Role_48.svg",
    "s3": "Res_Amazon-Simple-Storage-Service_Bucket_48.svg",
    "kms": "Arch_AWS-Key-Management-Service_48.svg",
    "bus": "Res_Amazon-EventBridge_Default-Event-Bus_48.svg",
    "rule": "Res_Amazon-EventBridge_Rule_48.svg",
    "cbus": "Res_Amazon-EventBridge_Custom-Event-Bus_48.svg",
    "acct": "AWS-Account_32.svg",
}


def resources(k):
    p = [k.txt(130, 26, "Kubernetes namespace", "h"), k.txt(330, 26, "IAM role", "h"), k.txt(470, 26, "Data store and key", "h", "start"),
         k.txt(900, 26, "Who else can reach it", "h"), k.box(12, 40, 236, 120)]
    p += [k.img(34, 64, "eks", 28), k.txt(54, 69, "shop-prod", "t", "start"), k.box(22, 92, 216, 44, "pill", 8),
          k.txt(34, 111, "Orders", "t", "start"), k.txt(34, 127, "orders-service", "m", "start")]
    p += [k.line(240, 114, 304, 114), k.txt(272, 106, "assumes", "s"), k.img(330, 114, "role", 40), k.txt(330, 146, "orders-role", "m")]
    p += [k.line(354, 114, 476, 114), k.img(500, 114, "s3", 40), k.img(544, 114, "kms", 26), k.txt(568, 111, "Order files", "t", "start"),
          k.txt(568, 127, "orders-prod", "m", "start"), k.chip(900, 114, "read", "chip")]
    return k.svg(1240, 180, "Resources for one environment", p)


def flow(k):
    p = [k.box(10, 30, 600, 170), k.box(630, 30, 600, 170), k.img(30, 52, "acct", 22), k.txt(48, 57, "Our account", "h", "start"),
         k.img(650, 52, "acct", 22), k.txt(668, 57, "Partner account", "h", "start")]
    p += [k.img(90, 130, "s3", 48), k.txt(90, 174, "orders bucket"), k.img(260, 130, "bus", 48), k.txt(260, 174, "default event bus"),
          k.img(430, 130, "rule", 48), k.txt(430, 174, "our rule"), k.img(760, 130, "cbus", 48), k.txt(760, 174, "partner event bus")]
    p += [k.line(116, 130, 232, 130), k.num(174, 130, 1), k.line(286, 130, 402, 130), k.num(344, 130, 2),
          k.line(456, 130, 732, 130), k.num(620, 130, 3)]
    return k.svg(1240, 210, "Notice flow", p)


def main():
    icon_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
    k = Kit(icon_dir, ICONS)
    body = f"""
  <h1>Orders storage, made up for the example</h1>
  <div class="key">What one environment gets, and how a new file reaches a partner account.</div>
  <section><h2>1. Everything created for one environment</h2>{resources(k)}
    <div class="legend">{k.legend_item("role", "IAM role")}{k.legend_item("s3", "S3 bucket")}{k.legend_item("kms", "encryption key")}</div></section>
  <section><h2>2. A notice for each new file</h2>{flow(k)}
    <ol class="steps"><li>A file lands in the bucket; S3 posts a notice to the default event bus.</li>
      <li>Our rule picks the notices for this bucket.</li><li>It sends them to the partner's event bus.</li></ol>
    <div class="gloss">{k.gloss_item("bus", "Default event bus", "comes with every account; AWS services post their events there.")}
      {k.gloss_item("rule", "Rule", "picks the events that match and sends them to a target.")}</div></section>
"""
    out.write_text(page("Orders storage example", body))
    return 0


if __name__ == "__main__":
    sys.exit(main())
