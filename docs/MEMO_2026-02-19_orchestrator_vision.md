# Memo: Context-Driven Orchestrator Vision for Intellectual Genealogy

> Date: 2026-02-19
> Author: Evgeny (captured by Claude Code)
> Status: Planning / Requirements Gathering

## Background

We had The Critic app which mostly had a lot of built-in flows. We then tried to move them into Analyzer-v2 (viewable at analyzer-mgmt): so we've set up Engines (genealogy-related - we have 11, fully refactored), Implementations, Stances, Operationalizations, and Views.

## Current State

- https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy — working genealogy page
- https://analyzer-mgmt-frontend.onrender.com/views/genealogy_conditions — fully wired up to the critic but only tested its Renderer capability

## The Problem

Still unclear how to fully replicate what we currently have on The Critic for genealogy but out of this new infrastructure. It's okay to rerun data analysis anew - we don't have to use all of Varoufakis but we can use some.

Still at a loss as to where other parts of the Varoufakis genealogy would come from... what are the views responsible for them? What kind of engines?

## The Vision — What Refactoring Was Meant to Achieve

a) **Never lose rich analysis** — we can do and store data as narrative and then parse as needed for UI rendering
b) **Experiment with UI on the fly** — it's configured in views
c) **Take advantage of layered analysis** — we can specify what engines/capabilities/level of depth to run, what to attach where through which context, etc.

## The Varoufakis Use Case

We are trying to understand the origins of his ideas in TECHNO-FEUDALISM book, keeping in mind that he wrote a 2026 follow-up essay on his Marxist origins — which means we'll need to:

1. Thoroughly examine his prior books, one by one, using various genealogy-specific engines (with multiple capabilities)
2. Think of sequencing
3. Synthesize this stuff
4. Think what views would be adequate to represent it using what UI

## The Key Insight: Context-Driven Orchestration

The kind of genealogy relevant for Varoufakis might differ from what genealogy we might need for Benanav or Slobodian or any of the other thinkers we'll be analyzing.

We need a **context-driven orchestrator** that will:

a) **Pick the right engines** with the right capabilities out of our menu
b) **Pick the right sequencing**, cross-exposure of their output
c) **Pick the right views/UI elements** — and will then parse the data coming from a and b correctly so that we can render as something other than beautiful text

## The Gap

We probably still assume that the user will be doing most of this heavy lifting. The user should be able to check the ingredients and make them deeper/refine them but the **ultimate curatorial decisions should be up to the LLM** who will be a much better judge of context.

We are almost there, but not quite because we probably have many individual capabilities but no orchestrator tasked with pulling them together.

## Next Steps

Plan this out — understand current state across both projects, identify what's missing, and design the orchestrator layer.
