

from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import UserUtteranceReverted, ConversationResumed, ConversationPaused, SlotSet
import os
import requests
import json
import logging

# MCP Service URL
MCP_SERVICE_URL = os.getenv("MCP_SERVICE_URL", "http://localhost:5003")


class ActionQueryEmployees(Action):
    """Query MongoDB via MCP service for employee info dynamically."""

    def name(self) -> Text:
        return "action_query_employees"

    def run(self, dispatcher: CollectingDispatcher,
                  tracker: Tracker,
                  domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        user_message = tracker.latest_message.get("text", "")
        try:
            # Make HTTP request to MCP service
            response = requests.post(f"{MCP_SERVICE_URL}/mcp/query", json={
                "method": "find",
                "params": {
                    "database": "mcp_database",
                    "collection": "employees",
                    "filter": {
                        "name": {"$regex": user_message, "$options": "i"}
                    },
                    "limit": 10
                }
            })
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success") and result.get("data"):
                    data = result["data"]
                    if "result" in data and len(data["result"]) > 0:
                        messages = []
                        for emp in data["result"]:
                            name = emp.get('name', 'Unknown')
                            position = emp.get('position', emp.get('role', 'N/A'))
                            department = emp.get('department', 'N/A')
                            messages.append(f"{name} - {position} ({department})")
                        dispatcher.utter_message(text="\n".join(messages))
                    else:
                        dispatcher.utter_message(text="Sorry, I could not find any employee matching your query.")
                else:
                    dispatcher.utter_message(text="Sorry, I could not retrieve employee information right now.")
            else:
                dispatcher.utter_message(text="Sorry, I am unable to query the database right now.")
                
        except Exception as e:
            logging.exception("MCP service query failed")
            dispatcher.utter_message(text="Sorry, I am unable to query the database right now.")
        
        return []

# Human handoff actions
class ActionDefaultFallback(Action):
    def name(self) -> Text:
        return "action_default_fallback"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        dispatcher.utter_message(response="utter_ask_human_help")
        return [SlotSet("handoff_offered", True)]


class ActionHandoff(Action):
    def name(self) -> Text:
        return "action_human_handoff"

    def run(self, dispatcher: CollectingDispatcher,
                  tracker: Tracker,
                  domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(text="Connecting you to a human agent... Type 'resume' to continue with the bot.")
        SENDER_ID = tracker.sender_id
        # Send handoff signal that backend can detect
        dispatcher.utter_message(json_message={"handoff": True, "user": SENDER_ID})
        return [ConversationPaused()]


class ActionCheckResume(Action):
    def name(self) -> Text:
        return "action_check_resume"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        user_message = tracker.latest_message.get("text", "").strip().lower()
        if user_message == "resume":
            dispatcher.utter_message(text="Conversation resumed with bot ✅")
            return [ConversationResumed()]
        else:
            dispatcher.utter_message(text="A human agent is handling your request. Type 'resume' to continue with the bot.")
            return [UserUtteranceReverted()]


class ActionResetHandoffSlot(Action):
    def name(self) -> Text:
        return "action_reset_handoff_slot"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        return [SlotSet("handoff_offered", None)]
