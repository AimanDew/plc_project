import json
import os
import urllib.request
import urllib.error
import urllib.parse


CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "erp_config.json")


def load_config():

    # ERP_CONFIG_PATH lets a script (or a shell env) swap which identity
    # ERPClient() authenticates as - e.g. erp_config.agent.json, so
    # fabricated/trial-run writes are attributed to the Agent user in the
    # Desk UI instead of Administrator - without touching call sites.
    path = os.environ.get("ERP_CONFIG_PATH", CONFIG_PATH)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class ERPClientError(Exception):

    def __init__(self, message, status_code=None, response_text=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class ERPClient:

    def __init__(self, config=None):

        self.config = config or load_config()
        self.base_url = self.config["erp_url"].rstrip("/")
        token = "token {}:{}".format(
            self.config["api_key"], self.config["api_secret"]
        )
        self.headers = {
            "Authorization": token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    # ------------------------------------------------------------------
    # low level
    # ------------------------------------------------------------------

    def _request(self, method, path, params=None, body=None):

        url = self.base_url + path

        if params:
            url += "?" + urllib.parse.urlencode(params)

        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(url, data=data, method=method)
        for k, v in self.headers.items():
            req.add_header(k, v)

        try:

            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else None

        except urllib.error.HTTPError as e:

            raw = e.read().decode("utf-8", errors="replace")
            raise ERPClientError(
                "ERPNext {} on {}: {}".format(e.code, path, raw),
                status_code=e.code,
                response_text=raw
            )

        except urllib.error.URLError as e:

            raise ERPClientError(
                "ERPNext unreachable: {}".format(e.reason),
                status_code=None,
                response_text=None
            )

    # ------------------------------------------------------------------
    # REST resource operations ( /api/resource/<doctype> )
    # ------------------------------------------------------------------

    def get_doc(self, doctype, name):

        path = "/api/resource/{}/{}".format(
            urllib.parse.quote(doctype), urllib.parse.quote(str(name))
        )
        return self._request("GET", path)

    def get_doc_list(self, doctype, filters=None, fields=None,
                     limit=20, order_by="modified desc"):

        params = {
            "limit_page_length": limit,
            "order_by": order_by
        }
        if filters:
            params["filters"] = json.dumps(filters)
        if fields:
            params["fields"] = json.dumps(fields)

        path = "/api/resource/{}".format(urllib.parse.quote(doctype))
        return self._request("GET", path, params=params)

    def insert_doc(self, doctype, fields):

        body = {"doctype": doctype, **fields}
        path = "/api/resource/{}".format(urllib.parse.quote(doctype))
        return self._request("POST", path, body=body)

    def update_doc(self, doctype, name, fields):

        # PUT .../<doctype>/<name> with {"fields": {...}} silently drops
        # child-table updates on some doctypes (e.g. Job Card) - go through
        # frappe.client.save instead, which runs the real doc.save() path.
        doc = self.get_doc(doctype, name)
        data = doc.get("data", doc) if isinstance(doc, dict) else doc
        data.update(fields)
        return self._request("POST", "/api/method/frappe.client.save", body={"doc": json.dumps(data)})

    def delete_doc(self, doctype, name):

        path = "/api/resource/{}/{}".format(
            urllib.parse.quote(doctype), urllib.parse.quote(str(name))
        )
        return self._request("DELETE", path)

    # ------------------------------------------------------------------
    # workflow actions (submit / cancel / amend on submittable docs)
    # ------------------------------------------------------------------

    def submit_doc(self, doctype, name):

        # PUT .../<doctype>/<name> with {"action": "submit"} is a silent no-op -
        # docstatus transitions must go through frappe.client.submit/cancel,
        # which actually calls doc.submit()/doc.cancel().
        doc = self.get_doc(doctype, name)
        data = doc.get("data", doc) if isinstance(doc, dict) else doc
        # doc goes in the POST body, not query params - a full doc (child
        # tables included) routinely exceeds the request-line length limit.
        return self._request("POST", "/api/method/frappe.client.submit", body={"doc": json.dumps(data)})

    def cancel_doc(self, doctype, name):

        return self._request(
            "POST",
            "/api/method/frappe.client.cancel",
            body={"doctype": doctype, "name": str(name)}
        )

    def save_doc(self, data):

        # For edits too large/complex for update_doc's field-patch shortcut
        # (e.g. child tables it silently drops on some doctypes) - takes a
        # full doc dict (as returned by get_doc/call_method) and saves it
        # through the same path the Desk UI uses.
        return self._request("POST", "/api/method/frappe.client.save", body={"doc": json.dumps(data)})

    # ------------------------------------------------------------------
    # whitelisted method calls ( /api/method/... )
    # ------------------------------------------------------------------

    def call_method(self, dotted_path, params=None, http_method="POST"):

        path = "/api/method/{}".format(dotted_path)
        return self._request(http_method, path, params=params)

    def ping(self):

        return self.call_method("ping", http_method="GET")

    def whoami(self):

        return self.call_method("frappe.auth.get_logged_user", http_method="GET")

    # ------------------------------------------------------------------
    # idempotency helper for the outbox sync
    # ------------------------------------------------------------------

    def find_by_source_uuid(self, doctype, event_uuid):

        result = self.get_doc_list(
            doctype,
            filters=[["source_uuid", "=", event_uuid]],
            limit=1
        )
        if isinstance(result, dict) and "data" in result:
            return result["data"][0] if result["data"] else None
        if isinstance(result, list) and result:
            return result[0]
        return None

    # ------------------------------------------------------------------
    # standards fetchers (for ERP-driven OEE calculation)
    # ------------------------------------------------------------------

    def get_active_job_card(self, workstation, status="Work In Progress"):

        result = self.get_doc_list(
            "Job Card",
            filters=[["workstation", "=", workstation],
                     ["status", "=", status]],
            fields=["name", "work_order", "operation", "workstation", "status"],
            limit=1
        )
        data = result.get("data", []) if isinstance(result, dict) else result
        return data[0] if data else None

    def get_workstation_standards(self, workstation):

        doc = self.get_doc("Workstation", workstation)
        data = doc.get("data", doc) if isinstance(doc, dict) else doc
        hours = []
        for row in (data.get("working_hours") or []):
            if row.get("enabled"):
                hours.append({
                    "start_time": row.get("start_time"),
                    "end_time": row.get("end_time")
                })
        return {
            "name": data.get("name"),
            "production_capacity": data.get("production_capacity"),
            "working_hours": hours
        }

    def get_bom_operation_standards(self, bom_no):

        # BOM Operation is a child table; query it via the Report/SQL-less path:
        # fetch the parent BOM doc and read its operations table
        doc = self.get_doc("BOM", bom_no)
        data = doc.get("data", doc) if isinstance(doc, dict) else doc
        ops = []
        for op in (data.get("operations") or []):
            ops.append({
                "operation": op.get("operation"),
                "workstation": op.get("workstation"),
                "time_in_mins": op.get("time_in_mins"),
            })
        return ops

    def get_work_order_standards(self, wo_name):

        doc = self.get_doc("Work Order", wo_name)
        data = doc.get("data", doc) if isinstance(doc, dict) else doc
        return {
            "name": data.get("name"),
            "item": data.get("production_item"),
            "bom_no": data.get("bom_no"),
            "qty": data.get("qty"),
            "produced_qty": data.get("produced_qty"),
            "status": data.get("status")
        }


if __name__ == "__main__":

    client = ERPClient()
    print("ping:", client.ping())
    print("whoami:", client.whoami())