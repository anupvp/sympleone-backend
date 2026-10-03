from pydantic import BaseModel, Field


class SalesTrendPointOut(BaseModel):
    date: str
    netSales: float
    netSalesAmount: float
    previousPeriod: float
    previousPeriodAmount: float
    orderCount: int
    previousPeriodOrderCount: int


class SalesTrendOut(BaseModel):
    frequency: str
    currencySymbol: str
    points: list[SalesTrendPointOut]


class ProfitabilitySegmentOut(BaseModel):
    id: str
    label: str
    amount: float
    percent: float
    color: str


class ProfitabilityNetProfitOut(BaseModel):
    label: str
    amount: str
    percent: float


class ProfitabilityOut(BaseModel):
    centerLabel: str
    centerValue: str
    segments: list[ProfitabilitySegmentOut]
    netProfit: ProfitabilityNetProfitOut


class StatCardOut(BaseModel):
    id: str
    label: str
    value: str
    changePercent: float
    comparisonLabel: str
    icon: str
    accent: str


class AlertActionItemOut(BaseModel):
    id: str
    count: int
    title: str
    tone: str
    href: str | None = None


class MarketplaceRowOut(BaseModel):
    id: str
    name: str
    slug: str
    gmv: str
    netSales: str
    orders: int
    profit: str
    profitPercent: float
    growthPercent: float
    sparkline: list[float] = Field(default_factory=list)
