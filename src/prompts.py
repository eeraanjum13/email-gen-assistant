"""Prompt templates for the email generation assistant."""

ADVANCED_SYSTEM = """\
You are a senior executive-communications assistant with 15 years of experience \
drafting professional emails for C-suite leaders across industries. You write \
with precision, adapt naturally to any tone, and never invent facts beyond what \
you are given."""

ADVANCED_USER_TEMPLATE = """\
You will draft a professional email. Follow this process:
1. In <thinking> tags, privately plan: map every key fact to a sentence, decide \
the opening hook and closing CTA, flag any gaps.
2. In <email> tags, write only the final email — no preamble, no explanation.

--- EXAMPLES ---

[Example 1 — Formal follow-up]
Intent: Follow up after a vendor meeting to request a proposal
Key facts:
1. Met on 2024-03-12
2. Discussed cloud-storage pricing
3. Need proposal by 2024-03-26
4. Contact is Sarah Chen
Tone: formal

<thinking>
Opening: thank Sarah for the meeting. Core ask: send proposal by 26 March. \
Closing: express anticipation of her response.
</thinking>
<email>
Dear Sarah,

Thank you for taking the time to meet with us on 12 March to discuss your \
cloud-storage pricing options. We appreciated the detailed walkthrough.

As discussed, could you please send us your formal proposal by 26 March? That \
will give our procurement team sufficient time to review before our Q2 planning \
cycle closes.

Looking forward to your response.

Best regards,
[Your name]
</email>

[Example 2 — Empathetic apology]
Intent: Apologise to a client for a missed delivery and offer a remedy
Key facts:
1. Order #4821
2. Delivery was due 2024-04-01
3. Delayed by warehouse fire
4. Rescheduled to 2024-04-08
5. Offering 15% discount
Tone: empathetic

<thinking>
Lead with personal apology, state the cause honestly, give the new date, \
offer the discount as a concrete gesture, close with openness to further help.
</thinking>
<email>
Dear [Client Name],

I want to reach out personally to apologise for the delay in delivering \
Order #4821. An unexpected warehouse fire on 1 April disrupted our fulfilment \
operations, pushing your delivery to 8 April.

I understand how frustrating it is when a commitment is missed, and we take full \
responsibility. As a sincere apology, we would like to offer you a 15% discount \
on this order.

Please let me know if there is anything else I can do to make this right.

Warm regards,
[Your name]
</email>

--- YOUR TASK ---

Intent: {intent}
Key facts:
{key_facts}
Tone: {tone}"""

NAIVE_TEMPLATE = """\
Write a professional email.
Intent: {intent}
Key facts: {key_facts}
Tone: {tone}"""


def format_facts(facts: list[str]) -> str:
    """Return facts as a numbered list string."""
    return "\n".join(f"{i + 1}. {fact}" for i, fact in enumerate(facts))
