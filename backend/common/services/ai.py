from backend.common.services.claude_service import explain


class AIProvider:
    def explain(self, question, facts):
        return explain(question, facts)
