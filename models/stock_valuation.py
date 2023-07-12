from odoo import fields, models, api, _


class InheritStockValuationAjdjustmentLines(models.Model):
    _inherit = "stock.valuation.adjustment.lines"

    cost_difference = fields.Float(
        string="Cost Difference", compute="_compute_cost_difference", store=True
    )
    price_difference = fields.Float(
        string="Price Difference", compute="_compute_price_difference", store=True
    )
    computed_price = fields.Float(string="Computed Price", readonly=True)
    new_price = fields.Float(string="New Price")
    old_price = fields.Float(string="Old Price")
    new_cost = fields.Float(string="New Cost")

    @api.depends("new_cost", "former_cost")
    def _compute_cost_difference(self):
        for record in self:
            record.cost_difference = record.final_cost - record.former_cost

    @api.depends("computed_price", "new_price")
    def _compute_price_difference(self):
        for record in self:
            record.price_difference = record.new_price - record.computed_price

    @api.onchange("new_price")
    def onchange_new_price(self):
        for record in self:
            record.new_cost = record.quantity * record.new_price
