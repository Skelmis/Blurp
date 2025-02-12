import datetime


from piccolo.table import Table
from piccolo.columns import Text, Timestamptz, UUID, Serial


class RequestMade(Table):
    id: Serial
    headers: str = Text(help_text="Headers as json string")
    body: str = Text(help_text="The body of the request")
    url: str = Text(help_text="The url a request was made to")
    query_params: str = Text(help_text="The query params in the url")
    made_at: datetime.datetime = Timestamptz(help_text="When the request was made")
    type: str = Text(help_text="Type of request made, think GET")
    uuid = UUID(help_text="A UUID instead of enumerable id", index=True)
    domain = Text(help_text="The domain this request was made to", default="")
