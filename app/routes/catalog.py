"""V2 catalog APIs; the shared access hook enforces role and CSRF permissions."""
from functools import wraps
import io
import json

from flask import Blueprint, g, jsonify, request, send_file
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.coal import Coal
from app.models.catalog import AssayRevision, CoalBatch
from app.services import catalog_service as service
from app.services.catalog_import import commit_import, export_catalog, preview_import

catalog_bp = Blueprint('catalog', __name__, url_prefix='/api')


def endpoint(function):
    @wraps(function)
    def handle(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except LookupError as exc:
            db.session.rollback()
            return jsonify(status='error', code='record_not_found', message=str(exc)), 404
        except service.CatalogConflict as exc:
            db.session.rollback()
            return jsonify(status='error', code='catalog_conflict', message=str(exc)), 409
        except IntegrityError:
            db.session.rollback()
            return jsonify(status='error', code='catalog_conflict', message='记录冲突，请刷新后重试'), 409
        except (ValueError, TypeError) as exc:
            db.session.rollback()
            return jsonify(status='error', code='invalid_request', message=str(exc)), 400
    return handle


def settings():
    from app.services.access_service import get_settings
    return get_settings()


def payload():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ValueError('请求必须为JSON对象')
    return body


def boolean_query(name, default=False):
    value = request.args.get(name)
    if value is None:
        return default
    if value not in ('true', 'false'):
        raise ValueError(f'{name}必须为true或false')
    return value == 'true'


def paginated(query, serializer):
    page = int(request.args.get('page', 1))
    size = int(request.args.get('page_size', 0))
    if page < 1 or size < 0 or size > 2000:
        raise ValueError('page须至少为1，page_size须在0..2000（0表示全部）')
    total = query.count()
    if size:
        query = query.offset((page - 1) * size).limit(size)
    return jsonify(status='success', data=[serializer(item) for item in query.all()],
                   pagination={'page': page, 'page_size': size, 'total': total})


@catalog_bp.route('/catalog', methods=['GET', 'POST'])
@endpoint
def catalog():
    current = settings()
    if request.method == 'POST':
        coal = service.create_coal(payload())
        db.session.commit()
        return jsonify(status='success', data=service.serialize_coal(coal, current)), 201
    query = Coal.query.order_by(Coal.id)
    if not boolean_query('include_archived'):
        query = query.filter_by(archived=False)
    if request.args.get('search'):
        query = query.filter(Coal.name.contains(request.args['search'], autoescape=True))
    return paginated(query, lambda coal: service.serialize_coal(coal, current))


@catalog_bp.patch('/catalog/<int:coal_id>')
@endpoint
def edit_coal(coal_id):
    coal = service.update_coal(coal_id, payload())
    db.session.commit()
    return jsonify(status='success', data=service.serialize_coal(coal, settings()))


@catalog_bp.route('/catalog/<int:coal_id>/batches', methods=['GET', 'POST'])
@endpoint
def batches(coal_id):
    service.get_coal(coal_id)
    current = settings()
    if request.method == 'POST':
        batch = service.create_batch(coal_id, payload())
        db.session.commit()
        return jsonify(status='success', data=service.serialize_batch(batch, current)), 201
    query = CoalBatch.query.filter_by(coal_id=coal_id).order_by(CoalBatch.id)
    if not boolean_query('include_archived'):
        query = query.filter_by(archived=False)
    return paginated(query, lambda batch: service.serialize_batch(batch, current))


@catalog_bp.patch('/batches/<int:batch_id>')
@endpoint
def edit_batch(batch_id):
    batch = service.update_batch(batch_id, payload())
    db.session.commit()
    return jsonify(status='success', data=service.serialize_batch(batch, settings()))


@catalog_bp.route('/batches/<int:batch_id>/assays', methods=['GET', 'POST'])
@endpoint
def assays(batch_id):
    service.get_batch(batch_id)
    current = settings()
    if request.method == 'POST':
        record = service.create_assay(batch_id, payload(), user_id=g.current_user.id)
        db.session.commit()
        return jsonify(status='success', data=service.serialize_assay(record, current)), 201
    return paginated(AssayRevision.query.filter_by(batch_id=batch_id).order_by(AssayRevision.revision.desc()),
                     lambda record: service.serialize_assay(record, current))


@catalog_bp.get('/assays')
@endpoint
def flat_assays():
    current = settings()
    query = AssayRevision.query.join(CoalBatch).join(Coal).order_by(AssayRevision.id)
    if not boolean_query('include_archived'):
        query = query.filter(Coal.archived.is_(False), CoalBatch.archived.is_(False))
    if request.args.get('coal_id'):
        query = query.filter(Coal.id == int(request.args['coal_id']))
    if request.args.get('batch_id'):
        query = query.filter(CoalBatch.id == int(request.args['batch_id']))
    return paginated(query, lambda record: service.serialize_assay(record, current))


@catalog_bp.post('/assays/preview')
@endpoint
def preview_assay():
    from app.services.assay_conversion import evaluate_assay, validate_raw_assay
    body = payload()
    service.object_fields(body, ('raw',))
    raw = validate_raw_assay(body.get('raw'))
    return jsonify(status='success', data={'raw': raw, 'eligibility': evaluate_assay(raw, settings())})


@catalog_bp.post('/catalog/import/preview')
@endpoint
def preview_upload():
    kwargs = {}
    if 'file' in request.files:
        uploaded = request.files['file']
        from app.services.catalog_import import MAX_BYTES
        kwargs.update(file_bytes=uploaded.read(MAX_BYTES + 1), filename=uploaded.filename)
        for field in ('mapping', 'metric_metadata', 'confirmed_headers'):
            if field in request.form:
                try:
                    kwargs[field] = json.loads(request.form[field])
                except json.JSONDecodeError:
                    raise ValueError(f'{field}须为JSON') from None
    else:
        body = payload()
        service.object_fields(body, ('text', 'mapping', 'metric_metadata', 'confirmed_headers'))
        kwargs = body
    return jsonify(status='success', data=preview_import(user_id=g.current_user.id, settings=settings(), **kwargs))


@catalog_bp.post('/catalog/import/commit')
@endpoint
def commit_upload():
    body = payload()
    service.object_fields(body, ('preview_token',))
    result = commit_import(body.get('preview_token'), user_id=g.current_user.id)
    db.session.commit()
    return jsonify(status='success', data=result), 201


@catalog_bp.get('/catalog/template')
@catalog_bp.get('/catalog/export')
@endpoint
def export_records():
    content, mime, filename = export_catalog(request.args.get('format', 'xlsx'),
                                             template=request.path.endswith('/template'),
                                             include_archived=boolean_query('include_archived', True))
    return send_file(io.BytesIO(content), mimetype=mime, as_attachment=True, download_name=filename)
