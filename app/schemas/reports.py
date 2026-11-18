from pydantic import BaseModel, Field


class FinanceTransactionOut(BaseModel):
    transactionId: str
    transactionType: str
    transactionStatus: str | None = None
    description: str | None = None
    postedDate: str
    amount: float
    currencyCode: str
    orderId: str | None = None
    settlementId: str | None = None
    shipmentId: str | None = None
    eventGroupId: str | None = None


class FinanceDailyPointOut(BaseModel):
    date: str
    netAmount: float
    count: int


class FinanceTypeBreakdownOut(BaseModel):
    transactionType: str
    totalAmount: float
    count: int


class FinancesReportOut(BaseModel):
    currencyCode: str
    dateFrom: str
    dateTo: str
    truncated: bool = False
    transactions: list[FinanceTransactionOut] = Field(default_factory=list)
    dailySeries: list[FinanceDailyPointOut] = Field(default_factory=list)
    byType: list[FinanceTypeBreakdownOut] = Field(default_factory=list)