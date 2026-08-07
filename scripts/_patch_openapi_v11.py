# -*- coding: utf-8 -*-
"""One-shot OpenAPI v1.1 design patch for stage 05.1. Not business code."""
from pathlib import Path

p = Path(r"D:\重构python\kwzy-python\docs\04-api\openapi-v1-core.yaml")
c = p.read_text(encoding="utf-8")

page_access = """
  /auth/page-access/send:
    post:
      tags: [Auth]
      summary: 发送高敏页面验证码（如催缴）
      operationId: authPageAccessSend
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [purpose]
              properties:
                purpose:
                  type: string
                  description: COLLECTION_SMS
                  example: COLLECTION_SMS
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ApiEnvelopeOk'

  /auth/page-access/verify:
    post:
      tags: [Auth]
      summary: 校验验证码并签发 page_access_proof
      operationId: authPageAccessVerify
      security: [{ bearerAuth: [] }]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [purpose, code]
              properties:
                purpose: { type: string }
                code: { type: string }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PageAccessProofResponse'

  /auth/codes:
    get:
      tags: [Auth]
      summary: 当前用户权限码列表
      operationId: authCodes
      security: [{ bearerAuth: [] }]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PermissionCodesResponse'

  /auth/logout:
    post:
      tags: [Auth]
      summary: 登出（作废 refresh）
      operationId: authLogout
      security: [{ bearerAuth: [] }]
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ApiEnvelopeOk'

"""

if "/auth/page-access/send" not in c:
    marker = "  /parks:\n"
    if marker not in c:
        raise SystemExit("marker parks not found")
    c = c.replace(marker, page_access + marker, 1)

party_extra = """
  /parties/{party_id}:
    get:
      tags: [Parties]
      summary: 入驻方详情
      operationId: getParty
      security: [{ bearerAuth: [] }]
      parameters:
        - name: party_id
          in: path
          required: true
          schema: { type: integer, format: int64 }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PartyEnvelope'
    patch:
      tags: [Parties]
      summary: 更新入驻方
      operationId: updateParty
      security: [{ bearerAuth: [] }]
      parameters:
        - name: party_id
          in: path
          required: true
          schema: { type: integer, format: int64 }
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/PartyUpdate'
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PartyEnvelope'

"""

if "/parties/{party_id}" not in c:
    c = c.replace("  /leases:\n", party_extra + "  /leases:\n", 1)

building_extra = """
  /buildings/{building_id}:
    get:
      tags: [Parks]
      summary: 楼栋详情
      operationId: getBuilding
      security: [{ bearerAuth: [] }]
      parameters:
        - name: building_id
          in: path
          required: true
          schema: { type: integer, format: int64 }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/BuildingEnvelope'
    patch:
      tags: [Parks]
      summary: 更新楼栋
      operationId: updateBuilding
      security: [{ bearerAuth: [] }]
      parameters:
        - name: building_id
          in: path
          required: true
          schema: { type: integer, format: int64 }
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/BuildingUpdate'
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/BuildingEnvelope'
    delete:
      tags: [Parks]
      summary: 删除楼栋（软删）
      operationId: deleteBuilding
      security: [{ bearerAuth: [] }]
      parameters:
        - name: building_id
          in: path
          required: true
          schema: { type: integer, format: int64 }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ApiEnvelopeOk'

"""

if "/buildings/{building_id}" not in c:
    c = c.replace("  /units:\n", building_extra + "  /units:\n", 1)

old_schemas = """  schemas:
    ApiOk:
      type: object
      properties:
        ok: { type: boolean, default: true }

    LoginRequest:"""

new_schemas = """  schemas:
    # ----- 统一响应 envelope（P0-3）-----
    ApiEnvelopeOk:
      type: object
      required: [code, message, data]
      properties:
        code: { type: string, example: OK }
        message: { type: string, example: success }
        data: { type: object, nullable: true }

    ErrorResponse:
      type: object
      required: [code, message, data]
      properties:
        code: { type: string, example: VALIDATION_ERROR }
        message: { type: string }
        data: { type: object, nullable: true }

    PageAccessProofResponse:
      type: object
      properties:
        code: { type: string, example: OK }
        message: { type: string }
        data:
          type: object
          properties:
            page_access_proof: { type: string }
            expires_in: { type: integer }

    PermissionCodesResponse:
      type: object
      properties:
        code: { type: string, example: OK }
        message: { type: string }
        data:
          type: object
          properties:
            codes:
              type: array
              items: { type: string }

    PartyEnvelope:
      type: object
      properties:
        code: { type: string }
        message: { type: string }
        data:
          $ref: '#/components/schemas/Party'

    BuildingEnvelope:
      type: object
      properties:
        code: { type: string }
        message: { type: string }
        data:
          $ref: '#/components/schemas/Building'

    BuildingUpdate:
      type: object
      properties:
        name: { type: string }
        building_type: { type: string }
        address: { type: string }
        description: { type: string }

    PartyUpdate:
      type: object
      properties:
        name: { type: string }
        contact_name: { type: string }
        contact_phone: { type: string }
        credit_code: { type: string }
        address: { type: string }
        status: { type: string }
        remark: { type: string }

    ApiOk:
      description: Prefer ApiEnvelopeOk — same envelope shape
      type: object
      properties:
        code: { type: string, default: OK }
        message: { type: string, default: success }
        data: { type: object, nullable: true }

    LoginRequest:"""

if "ErrorResponse:" not in c:
    if old_schemas not in c:
        raise SystemExit("schemas marker not found")
    c = c.replace(old_schemas, new_schemas, 1)

if "is_overdue:" not in c:
    old_bill = """    Bill:
      type: object
      properties:
        id: { type: integer, format: int64 }
        bill_no: { type: string }
        park_id: { type: integer, format: int64 }
        party_id: { type: integer, format: int64 }
        contract_id: { type: integer, format: int64, nullable: true }
        period_start: { type: string, format: date }
        period_end: { type: string, format: date }
        due_date: { type: string, format: date, nullable: true }
        status: { type: string }
        total_amount: { type: number }
        paid_amount: { type: number }
        source: { type: string }
        lines:
          type: array
          items:
            $ref: '#/components/schemas/BillLine'"""
    new_bill = """    Bill:
      type: object
      description: |
        账单。status 仅限 DRAFT|ISSUED|PARTIALLY_PAID|PAID|VOID|DISCARDED。
        禁止 OVERDUE 主状态；逾期见 is_overdue。
      properties:
        id: { type: integer, format: int64 }
        bill_no: { type: string }
        park_id: { type: integer, format: int64 }
        party_id: { type: integer, format: int64 }
        contract_id: { type: integer, format: int64, nullable: true }
        period_start: { type: string, format: date }
        period_end: { type: string, format: date }
        due_date: { type: string, format: date, nullable: true }
        overdue_since: { type: string, format: date, nullable: true }
        status:
          type: string
          enum: [DRAFT, ISSUED, PARTIALLY_PAID, PAID, VOID, DISCARDED]
        total_amount: { type: number }
        paid_amount: { type: number }
        open_amount: { type: number, description: total_amount - paid_amount }
        is_overdue:
          type: boolean
          description: 衍生字段；逾期且未结清
        source: { type: string }
        lines:
          type: array
          items:
            $ref: '#/components/schemas/BillLine'"""
    if old_bill not in c:
        raise SystemExit("Bill schema block not found")
    c = c.replace(old_bill, new_bill, 1)

pay_old = """    Payment:
      type: object
      properties:
        id: { type: integer, format: int64 }
        payment_no: { type: string }"""
pay_new = """    Payment:
      type: object
      description: |
        收款登记凭证（运营侧登记实收并核销账单）。
        不是租户在线支付订单；在线收银台为二期。
      properties:
        id: { type: integer, format: int64 }
        payment_no: { type: string }"""
if "不是租户在线支付订单" not in c:
    if pay_old not in c:
        raise SystemExit("Payment schema not found")
    c = c.replace(pay_old, pay_new, 1)

idem = """    BillIdPath:
      name: bill_id
      in: path
      required: true
      schema: { type: integer, format: int64 }

  schemas:"""
idem_new = """    BillIdPath:
      name: bill_id
      in: path
      required: true
      schema: { type: integer, format: int64 }
    IdempotencyKey:
      name: Idempotency-Key
      in: header
      required: false
      schema: { type: string }
      description: 写操作幂等键（payments 创建、bills issue 等必须支持）

  schemas:"""
if "IdempotencyKey:" not in c:
    if idem not in c:
        raise SystemExit("BillIdPath block not found")
    c = c.replace(idem, idem_new, 1)

if "name: is_overdue" not in c:
    filt_old = """        - name: period_end
          in: query
          schema: { type: string, format: date }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/BillPage'"""
    filt_new = """        - name: period_end
          in: query
          schema: { type: string, format: date }
        - name: is_overdue
          in: query
          description: true=仅逾期未结（衍生条件，非 status=OVERDUE）
          schema: { type: boolean }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/BillPage'"""
    if filt_old not in c:
        raise SystemExit("bill list filter block not found")
    c = c.replace(filt_old, filt_new, 1)

c = c.replace(
    "summary: 登记收款并核销",
    "summary: 收款登记并核销账单（非在线支付下单）",
)

# Note at top for envelope convention
if "响应约定" not in c:
    c = c.replace(
        "    覆盖：认证、园区/单元、合同、账单、收款催缴、线索转化。\n",
        "    覆盖：认证、园区/单元、合同、账单、收款催缴、线索转化。\n"
        "    响应约定：成功/失败均为 {code, message, data}；错误见 ErrorResponse。\n"
        "    路径与字段一律 snake_case。\n",
        1,
    )

p.write_text(c, encoding="utf-8")
print("openapi patched")
print("is_overdue", "is_overdue" in c)
print("page-access", "/auth/page-access/send" in c)
print("party_id", "/parties/{party_id}" in c)
print("ErrorResponse", "ErrorResponse:" in c)
print("IdempotencyKey", "IdempotencyKey:" in c)
