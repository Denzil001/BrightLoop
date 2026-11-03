"""Independent transactions cannot combine two valid edits into a negative price."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from conftest import test_engine
from app.api.v1.endpoints.products import update_product, update_product_variant
from app.core.security import hash_password
from app.models.catalog import Product, ProductVariant
from app.models.users import User
from app.schemas.catalog import ProductUpdate, ProductVariantUpdate


def test_base_and_variant_edits_serialize_on_the_parent():
    ids = {}
    try:
        with Session(test_engine) as db:
            actor = User(name="Catalog race actor", email_normalized=f"catalog_race_{uuid.uuid4().hex}@brightloop.test", role="ADMIN", active=True, password_hash=hash_password("Catalog@Secure123"))
            product = Product(name=f"Catalog race {uuid.uuid4().hex}", type="ADDON", sales_price=10, cost_price=0)
            db.add_all([actor, product]); db.flush()
            variant = ProductVariant(product_id=product.id, name="Race variant", price_adjustment=0)
            db.add(variant); db.flush()
            ids.update(actor=actor.id, product=product.id, variant=variant.id)
            db.commit()
        ready = threading.Event()
        connection = {}

        def adjust():
            with Session(test_engine) as db:
                connection["pid"] = db.scalar(text("select pg_backend_pid()"))
                actor = db.get(User, ids["actor"])
                ready.set()
                try:
                    update_product_variant(ids["product"], ids["variant"], ProductVariantUpdate(price_adjustment="-10.00"), db, actor)
                    return 200
                except HTTPException as error:
                    db.rollback()
                    return error.status_code

        with ThreadPoolExecutor(max_workers=1) as pool:
            with Session(test_engine) as first:
                first.scalar(select(Product).where(Product.id == ids["product"]).with_for_update())
                future = pool.submit(adjust)
                try:
                    assert ready.wait(5)
                    deadline, blocked = time.monotonic() + 5, False
                    while time.monotonic() < deadline:
                        with Session(test_engine) as observer:
                            blocked = observer.scalar(text("select wait_event_type = 'Lock' from pg_stat_activity where pid = :pid"), {"pid": connection["pid"]})
                        if blocked:
                            break
                        time.sleep(0.01)
                    assert blocked, "The variant writer must wait for the locked parent product."
                    update_product(ids["product"], ProductUpdate(sales_price="0.00"), first, first.get(User, ids["actor"]))
                finally:
                    first.rollback()
            assert future.result(timeout=5) == 422
        with Session(test_engine) as db:
            assert db.get(Product, ids["product"]).sales_price == 0
            assert db.get(ProductVariant, ids["variant"]).price_adjustment == 0
    finally:
        with Session(test_engine) as db:
            if "variant" in ids: db.execute(delete(ProductVariant).where(ProductVariant.id == ids["variant"]))
            if "product" in ids: db.execute(delete(Product).where(Product.id == ids["product"]))
            if "actor" in ids: db.execute(delete(User).where(User.id == ids["actor"]))
            db.commit()
