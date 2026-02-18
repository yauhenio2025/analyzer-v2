"""View definitions — declarative specs for how analytical outputs become UI.

A ViewDefinition declares: this data source -> this renderer type -> this
position in this app. Pure definition, no execution code. Consumer apps
interpret the definition and dispatch to their own component library.
"""
