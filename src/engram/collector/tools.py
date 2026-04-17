"""Typed tool command models for the imprint collector."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class AddImprintCommand(BaseModel):
    name: Literal["add_imprint"] = "add_imprint"
    text: str
    scope: str
    repo: str | None = None
    tags: list[str] = Field(default_factory=list)


class SearchImprintsCommand(BaseModel):
    name: Literal["search_imprints"] = "search_imprints"
    query: str
    scope: str | None = None
    repo: str | None = None


class UpdateImprintCommand(BaseModel):
    name: Literal["update_imprint"] = "update_imprint"
    id: str
    text: str | None = None
    scope: str | None = None
    tags: list[str] | None = None


class DeleteImprintCommand(BaseModel):
    name: Literal["delete_imprint"] = "delete_imprint"
    id: str


class ListImprintsCommand(BaseModel):
    name: Literal["list_imprints"] = "list_imprints"
    scope: str | None = None


ToolCommand = Annotated[
    AddImprintCommand
    | SearchImprintsCommand
    | UpdateImprintCommand
    | DeleteImprintCommand
    | ListImprintsCommand,
    Field(discriminator="name"),
]
