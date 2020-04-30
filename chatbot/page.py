class Page:
    def __init__(self, client, title):
        self.title = title
        self.client = client
        query = self.client.session.post(self.client.site + "api.php", data={
            "action": "query",
            "prop": "info|revisions",
            "titles": self.title,
            "indexpageids": True,
            "rvprop": "content",
            "intoken": "edit",
            "format": "json",
        }).json()["query"]
        page_id = query["pageids"][0]
        page = query["pages"][page_id]
        self.content = page["revisions"][0]["*"] if page_id != "-1" else ""
        self.edit_token = page["edittoken"]

    def save(self, summary=""):
        self.client.session.post(self.client.site + "api.php", data={
            "action": "edit",
            "title": self.title,
            "text": self.content,
            "token": self.edit_token,
            "bot": True,
            "minor": True,
            "summary": summary,
            "format": "json",
        }).json()
