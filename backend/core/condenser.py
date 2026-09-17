from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from llama_index.core.prompts import PromptTemplate

CONDENSE_PROMPT_TEMPLATE = """\
Given the following conversation and a follow up question, rephrase the follow up question to be a standalone question.
Match the language of the follow up input (Persian if asked in Persian, English if asked in English).

CRITICAL INSTRUCTION FOR CODE & TECHNICAL QUERIES:
If the follow-up question contains code snippets, function calls, SQL queries, commands, or technical identifiers, DO NOT alter, translate, or remove the code. Keep all code snippets and technical identifiers exactly as written, and formulate the conversational context around them. Do not treat English code as a reason to translate Persian questions into English.

Chat History:
{chat_history_str}

Follow Up Input: {query}
Standalone question:"""


class CondenseQuestionPipeline:
    """Pipeline to rewrite questions based on chat history.

    Replaces pronouns or references in a user's question with the correct
    entities from the prior conversation to ensure accurate vector DB retrieval.
    """

    def __init__(self) -> None:
        self.llm = Settings.llm
        self.prompt_template = PromptTemplate(CONDENSE_PROMPT_TEMPLATE)

    def condense(self, query: str, chat_history: list[ChatMessage]) -> str:
        """Condenses the current query based on chat history.

        Args:
            query (str): The raw user query.
            chat_history (list[ChatMessage]): The previous conversation history.

        Returns:
            str: The condensed, standalone query.
        """
        if not chat_history:
            return query

        chat_history_str = "\n".join(
            [f"{msg.role.value.capitalize()}: {msg.content}" for msg in chat_history]
        )

        prompt = self.prompt_template.format(
            chat_history_str=chat_history_str, query=query
        )

        response = self.llm.complete(prompt)
        return str(response).strip()
