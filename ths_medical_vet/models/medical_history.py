# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class MedicalHistorySummary(models.Model):
    _name = 'vet.medical.history.summary'
    _description = 'Pet Medical History Summary'
    _auto = False  # This is a database view

    pet_id = fields.Many2one('res.partner', string='Pet', readonly=True)
    owner_id = fields.Many2one('res.partner', string='Owner', readonly=True)
    encounter_count = fields.Integer(string='Total Encounters', readonly=True)
    last_visit_date = fields.Datetime(string='Last Visit', readonly=True)
    vaccination_count = fields.Integer(string='Vaccinations', readonly=True)
    expired_vaccinations = fields.Integer(string='Expired Vaccinations', readonly=True)
    boarding_count = fields.Integer(string='Boarding Stays', readonly=True)

    # def init(self):
    #     """Create the vet_medical_history_summary SQL view."""
    #     self.env.cr.execute("""
    #         CREATE OR REPLACE VIEW vet_medical_history_summary AS (
    #             SELECT
    #                 row_number() OVER () AS id,
    #                 p.id AS pet_id,
    #                 p.ths_pet_owner_id AS owner_id,
    #                 COALESCE(enc.encounter_count, 0) AS encounter_count,
    #                 enc.last_visit_date,
    #                 COALESCE(vac.vaccination_count, 0) AS vaccination_count,
    #                 COALESCE(vac.expired_count, 0) AS expired_vaccinations,
    #                 COALESCE(brd.boarding_count, 0) AS boarding_count
    #             FROM res_partner p
    #             LEFT JOIN (
    #                 SELECT
    #                     ths_patient_ids,
    #                     COUNT(*) AS encounter_count,
    #                     MAX(date_start) AS last_visit_date
    #                 FROM ths_medical_base_encounter
    #                 WHERE state != 'cancelled'
    #                 GROUP BY ths_patient_ids
    #             ) enc ON enc.patient_ids = p.id
    #             LEFT JOIN (
    #                 SELECT
    #                     pet_id,
    #                     COUNT(*) AS vaccination_count,
    #                     SUM(CASE WHEN is_expired THEN 1 ELSE 0 END) AS expired_count
    #                 FROM vet_vaccination
    #                 GROUP BY pet_id
    #             ) vac ON vac.pet_id = p.id
    #             LEFT JOIN (
    #                 SELECT
    #                     pet_id,
    #                     COUNT(*) AS boarding_count
    #                 FROM vet_boarding_stay
    #                 WHERE state != 'cancelled'
    #                 GROUP BY pet_id
    #             ) brd ON brd.pet_id = p.id
    #             LEFT JOIN ths_partner_type tpt ON p.ths_partner_type_id = tpt.id
    #             WHERE tpt.name = 'Pet'
    #         )
    #     """)
