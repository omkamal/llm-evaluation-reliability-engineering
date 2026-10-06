"""One quota manager per provider: chats first, background work borrows only what chats are not using.

Tokens borrowed this minute are not handed back until the minute rolls over, so part of the chat
reserve (`held`) is never lent: a chat that arrives after background work borrowed still gets in."""


class QuotaManager:
    def __init__(self, tpm=100_000, reserve=0.6, held=0.3):
        self.tpm, self.reserve, self.held = tpm, reserve, held   # shares of the minute's tokens
        self.used = {"interactive": 0, "background": 0}
        self.chat_waiting = False   # True while chats are queued

    def admit(self, lane, tokens):
        if sum(self.used.values()) + tokens > self.tpm:
            return "shed" if lane == "background" else "wait"       # chats wait; background is shed
        if lane == "background":
            keep = self.reserve if self.chat_waiting else self.held
            if self.used["background"] + tokens > (1 - keep) * self.tpm:
                return "defer"      # never the share kept for chats
        self.used[lane] += tokens
        return "admit"

    def new_minute(self):
        self.used = {"interactive": 0, "background": 0}
