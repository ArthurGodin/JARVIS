class BaseAction:
    """
    Base de todas as ações. O método execute() pode retornar:
    - bool: True (sucesso) | False (falha sem detalhe)
    - tupla (bool, str): segundo elemento é a mensagem de erro/sucesso para o log/UI

    O executor aceita ambos os formatos.
    """

    def execute(self, action_config: dict, global_config: dict):
        raise NotImplementedError("As acoes devem implementar o metodo execute()")
