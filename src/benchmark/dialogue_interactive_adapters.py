from dataclasses import replace
import re

from typing import Tuple, Optional

from benchmark.adapter import (
    InteractionTrace,
    InteractiveAdapter,
    RequestState,
    UserInput,
    AdapterSpec,
    InteractionRound,
)

from benchmark.scenario import Instance
from benchmark.dialogue_scenarios import DialogueInstance
from benchmark.interaction_server.blacklist import contains_offensive, initialize_blacklist


class DialogueAdapter(InteractiveAdapter):
    def __init__(self, user_initiated, user_name: str, agent_name: str):
        super().__init__(user_initiated)
        self.user_name = user_name
        self.agent_name = agent_name
        self.blacklist, self.blacklist_max_len = initialize_blacklist()

    def _get_agent_name(self, instance: Instance) -> Optional[str]:
        if not isinstance(instance, DialogueInstance):
            return None
        if self.user_initiated:
            return getattr(instance.listener, "name", None)
        else:
            return getattr(instance.initiator, "name", None)

    def _get_user_name(self, instance: Instance) -> Optional[str]:
        if not isinstance(instance, DialogueInstance):
            return None
        if self.user_initiated:
            return getattr(instance.initiator, "name", None)
        else:
            return getattr(instance.listener, "name", None)

    def adapt_user_input_string(self, inp: str, name: Optional[str] = None) -> str:
        """Adapts user input string by prepending user_name"""
        inp = inp.strip()
        if name is None:
            name = self.user_name
        adapted_utterance = ': <span class="conversation_utterance_'+name+'">"' + inp + '"</span>'
        return adapted_utterance

    def postprocess_initial_request(
        self, initial_request_state: RequestState, adapter_spec: AdapterSpec
    ) -> RequestState:
        if self.user_initiated:

            print("Before postprocessing")
            print(initial_request_state.request.prompt)
            # Remove prompt
            new_prompt = re.sub(
                adapter_spec.input_prefix + ".*(?=" + adapter_spec.output_prefix + ")",
                "",
                initial_request_state.request.prompt,
            )
            new_request = replace(initial_request_state.request, prompt=new_prompt)
            initial_request_state = replace(initial_request_state, request=new_request)
            print("After postprocessing")
            print(initial_request_state.request.prompt)
        return initial_request_state

    def agent_prompt(self, name: Optional[str] = None) -> str:
        if name is None:
            name = self.agent_name
        agent_prompt = name + ': <span class="conversation_utterance_'+name+'">"'
        return agent_prompt

    def initial_lm_request(self, initial_request_state: RequestState) -> RequestState:
        initial_prompt = initial_request_state.request.prompt
        agent_name = self._get_agent_name(initial_request_state.instance)
        new_prompt = initial_prompt + self.agent_prompt(agent_name)
        new_request = replace(initial_request_state.request, prompt=new_prompt)
        new_request_state = replace(initial_request_state, request=new_request)
        return new_request_state

    def filter_toxic_generations(self, interaction_round: InteractionRound) -> Tuple[str, bool]:
        if interaction_round.request_state.result is None:
            return "", False
        bot_utterance = interaction_round.request_state.result.completions[0].text
        if contains_offensive(bot_utterance, self.blacklist, self.blacklist_max_len):
            return "Let's talk about something else", True
        return "", False

    def adapt_user_input(self, interaction_trace: InteractionTrace, user_input: UserInput) -> RequestState:
        user_name = self._get_user_name(interaction_trace.instance)
        agent_name = self._get_agent_name(interaction_trace.instance)
        adapted_user_input = self.adapt_user_input_string(user_input.input, user_name)
        assert len(interaction_trace.trace) > 0
        last_request_state = interaction_trace.trace[-1].request_state
        last_prompt = last_request_state.request.prompt
        last_response = ""
        if last_request_state.result and len(last_request_state.result.completions) > 0:
            last_response = last_request_state.result.completions[0].text
        new_prompt = (
            last_prompt + last_response + '"</span>\n' + adapted_user_input + "\n" + self.agent_prompt(agent_name)
        )
        new_request = replace(last_request_state.request, prompt=new_prompt)
        new_request_state = replace(last_request_state, request=new_request)
        return new_request_state
