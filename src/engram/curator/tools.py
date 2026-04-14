"""Typed tool command models for the curation agent."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class AddPreferenceCommand(BaseModel):
    name: Literal["add_preference"] = "add_preference"
    text: str
    scope: str
    repo: str | None = None
    tags: list[str] = Field(default_factory=list)


class SearchPreferencesCommand(BaseModel):
    name: Literal["search_preferences"] = "search_preferences"
    query: str
    scope: str | None = None
    repo: str | None = None


class UpdatePreferenceCommand(BaseModel):
    name: Literal["update_preference"] = "update_preference"
    id: str
    text: str | None = None
    scope: str | None = None
    tags: list[str] | None = None


class DeletePreferenceCommand(BaseModel):
    name: Literal["delete_preference"] = "delete_preference"
    id: str


class ListPreferencesCommand(BaseModel):
    name: Literal["list_preferences"] = "list_preferences"
    scope: str | None = None


ToolCommand = Annotated[
    AddPreferenceCommand
    | SearchPreferencesCommand
    | UpdatePreferenceCommand
    | DeletePreferenceCommand
    | ListPreferencesCommand,
    Field(discriminator="name"),
]
