"""One quota manager per provider: chats first, background work borrows only what chats are not using."""


class QuotaManager:
    def __init__(self, tpm=100_000, reserve=0.6):
        self.tpm, self.reserve = tpm, reserve          # tokens per minute; share held back for chats
        self.used = {"interactive": 0, "background": 0}
        self.chat_waiting = False   # True while chats are queued

    def admit(self, lane, tokens):
        if sum(self.used.values()) + tokens > self.tpm:
            return "shed" if lane == "background" else "wait"       # chats wait; background is shed
        own_share = (1 - self.reserve) * self.tpm
        borrowed = self.used["background"] + tokens > own_share
        if lane == "background" and self.chat_waiting and borrowed:
            return "defer"   # borrowing stops when chats surge
        self.used[lane] += tokens
        return "admit"

    def new_minute(self):
        self.used = {"interactive": 0, "background": 0}
