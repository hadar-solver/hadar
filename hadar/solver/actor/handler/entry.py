from copy import deepcopy
from typing import Any, Tuple

from hadar.solver.actor.handler.handler import State
from hadar.solver.actor.handler.handler import *


class StartHandler(Handler):
    """
    When Start message receive:
     |__ propose free production
    """

    def __init__(self, params: HandlerParameter):
        """
        Initiate handler.

        :param params: handler parameters to use
        """
        Handler.__init__(self, params=params)
        self.handler = ProposeFreeProductionHandler(params=params, next=ReturnHandler())

    def execute(self, state: State, message=None) -> Tuple[State, Any]:
        """
        Execute handler.

        :param state: current actor state
        :param message: Start message
        :return: next actor state
        """
        return self.handler.execute(deepcopy(state), deepcopy(message))


class CanceledCustomerExchangeHandler(Handler):
    """
    When CancelCustomerExchangeHandler
     |_ cancel exportation
        |_ if it's node producer : propose free production
    """
    def __init__(self, params: HandlerParameter):
        """
        Initiate handler.

        :param params: handler parameters to use
        """
        Handler.__init__(self, params=params)
        self.handler = CancelExportationHandler(params=params,
                    next=BackwardMessageHandler(type='tell',
                            after_backward=ReturnHandler(),
                            on_resume=ProposeFreeProductionHandler(next=ReturnHandler()),
                    ))

    def execute(self, state: State, message=None) -> Tuple[State, Any]:
        """
        Execute handler.

        :param state: current actor state
        :param message: CancelCustomerExchange message
        :return: next actor state
        """
        return self.handler.execute(deepcopy(state), deepcopy(message))


class ProposalOfferHandler(Handler):
    """
    When receive proposal offer:
     |_ check border capacity
       |_ if node is transfer, wait response
         |_ save final exchanges
       |_ if node is producer, check production capacity
         |_ save final exchanges
    """
    def __init__(self, params: HandlerParameter):
        """
        Initiate handler.

        :param params: handler parameters to use
        """
        Handler.__init__(self, params=params)
        self.handler = CheckOfferBorderCapacityHandler(params=params,
                    next=BackwardMessageHandler(type='ask',
                        after_backward=SaveExchangeHandler(exchange_type='transfer', next=ReturnHandler()),
                        on_resume=AcceptExchangeHandler(
                            next=SaveExchangeHandler(exchange_type='export', next=ReturnHandler()))
                    ))

    def execute(self, state: State, message: Any = None) -> Tuple[State, Any]:
        """
        Execute handler.

        :param state: current actor state
        :param message: ProposalOffer message
        :return: next actor state, list of exchanges
        """
        return self.handler.execute(deepcopy(state), deepcopy(message))


class ProposalHandler(Handler):
    """
    When receive proposal:
    |_ compare proposal with current state
      |_ if useless
        |_ forward proposal
      |_ if useful
        |_ make an offer, wait response
          |_ save exchanges accepted by producer
            |_ compute new adequacy
              |_ propose free production
              |_ cancel useless importation
    """
    def __init__(self, params: HandlerParameter):
        """
        Initiate handler.

        :param params: handler parameters to use
        """
        Handler.__init__(self, params=params)
        self.handler = CompareNewProduction(params=params,
                            for_prod_useless=ForwardMessageHandler(next=ReturnHandler()),
                            for_prod_useful=MakerOfferHandler(
                                next=SaveExchangeHandler(exchange_type='import',
                                    next=AdequacyHandler(
                                        next=ProposeFreeProductionHandler(
                                            next=CancelUselessImportationHandler(next=ReturnHandler())
                                        )
                                    )
                                )
                            ))

    def execute(self, state: State, message: Any = None) -> Tuple[State, Any]:
        """
        Execute handler.

        :param state: current actor state
        :param message: ProposalOffer message
        :return: next actor state
        """
        return self.handler.execute(deepcopy(state), deepcopy(message))
