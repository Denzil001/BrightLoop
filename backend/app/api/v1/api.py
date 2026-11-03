from fastapi import APIRouter, Depends
from app.api.contracts import validate_query_parameters
from app.api.v1.endpoints import (
    auth,
    customers,
    discounts,
    health,
    meta,
    plans,
    pricing,
    products,
    profile,
    staff,
    billing_runs,
    invoices,
    payments,
    reporting,
    subscriptions,
    taxes,
    templates,
)

api_router = APIRouter(dependencies=[Depends(validate_query_parameters)])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(meta.router, tags=["metadata"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(staff.router, prefix="/staff", tags=["staff"])
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])
api_router.include_router(products.router, prefix="/products", tags=["products"])
api_router.include_router(plans.router, prefix="/plans", tags=["plans"])
api_router.include_router(taxes.router, prefix="/taxes", tags=["taxes"])
api_router.include_router(discounts.router, prefix="/discounts", tags=["discounts"])
api_router.include_router(
    templates.router, prefix="/quotation-templates", tags=["quotation-templates"]
)
api_router.include_router(pricing.router, prefix="/pricing", tags=["pricing"])
api_router.include_router(subscriptions.router, prefix="/subscriptions", tags=["subscriptions"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
api_router.include_router(billing_runs.router, prefix="/billing-runs", tags=["billing-runs"])
api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
api_router.include_router(reporting.router, tags=["dashboard", "reports"])
