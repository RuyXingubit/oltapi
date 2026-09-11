from typing import Optional
from pydantic import BaseModel, Field


class Link(BaseModel):
    """Representação de um hiperlink HATEOAS / HAL enxuto."""
    href: str = Field(..., description="Caminho relativo da API para a ação ou recurso")
    method: str = Field(default="GET", description="Método HTTP requerido para a ação")
    description: Optional[str] = Field(default=None, description="Descrição amigável da ação")
