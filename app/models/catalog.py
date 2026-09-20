"""Coal masters have batches; every assay correction creates a new revision."""
from sqlalchemy import event

from app.extensions import db


class CoalBatch(db.Model):
    __tablename__ = 'coal_batches'
    __table_args__ = (db.UniqueConstraint('coal_id', 'code', name='uq_coal_batch_code'),)

    id = db.Column(db.Integer, primary_key=True)
    coal_id = db.Column(db.Integer, db.ForeignKey('coal_data.id'), nullable=False, index=True)
    code = db.Column(db.String(100), nullable=False)
    supplier = db.Column(db.String(100))
    received_at = db.Column(db.String(40))
    archived = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.current_timestamp())
    coal = db.relationship('Coal', backref=db.backref('batches', lazy='select'))


class AssayRevision(db.Model):
    __tablename__ = 'assay_revisions'
    __table_args__ = (db.UniqueConstraint('batch_id', 'revision', name='uq_batch_assay_revision'),)

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('coal_batches.id'), nullable=False, index=True)
    revision = db.Column(db.Integer, nullable=False)
    raw = db.Column(db.JSON, nullable=False)
    report_number = db.Column(db.String(120))
    sampled_at = db.Column(db.String(40))
    notes = db.Column(db.Text)
    source = db.Column(db.String(32), nullable=False, default='manual', server_default='manual')
    created_by = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.current_timestamp())
    batch = db.relationship('CoalBatch', backref=db.backref('assays', lazy='select', order_by='AssayRevision.revision'))


class ImportPreview(db.Model):
    __tablename__ = 'catalog_import_previews'

    token_hash = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    consumed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.current_timestamp())


@event.listens_for(AssayRevision, 'before_update')
def _immutable_update(mapper, connection, target):
    raise ValueError('化验修订不可修改；请新增修订')


@event.listens_for(AssayRevision, 'before_delete')
def _immutable_delete(mapper, connection, target):
    raise ValueError('化验修订不可删除；请归档批次')
