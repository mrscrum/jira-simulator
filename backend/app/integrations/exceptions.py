class JiraApiError(Exception):
    pass


class JiraAuthError(JiraApiError):
    pass


class JiraNotFoundError(JiraApiError):
    pass


class JiraRateLimitError(JiraApiError):
    def __init__(self, retry_after: float = 60.0):
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after {retry_after}s")


class JiraConnectionError(JiraApiError):
    pass
