"""Python Anesthesia Simulator.

@author: Aubouin--Pairault Bob 2023, bob.aubouin@tutanota.com
"""
# Standard import

# Third party imports
import numpy as np
import control
import pandas as pd
import casadi as cas
# Local imports
from .pk_models import CompartmentModel
from .pd_models import BIS_model, TOL_model, Hemo_PD_model


class Patient:
    """Define a Patient class able to simulate Anesthesia process."""

    def __init__(self,
                 patient_characteristic: list,
                 co_base: float = 6.5,
                 map_base: float = 90,
                 model_propo: str = 'Schnider',
                 model_remi: str = 'Minto',
                 ts: float = 1,
                 hill_param: list = None,
                 random_PK: bool = False,
                 random_PD: bool = False,
                 co_update: bool = False,
                 save_data_bool: bool = True):
        """
        Initialise a patient class for anesthesia simulation.

        Parameters
        ----------
        Patient_characteristic: list
            Patient_characteristic = [age (yr), height(cm), weight(kg), gender(0: female, 1: male)]
        co_base : float, optional
            Initial cardiac output. The default is 6.5L/min.
        map_base : float, optional
            Initial Mean Arterial Pressure. The default is 90mmHg.
        model_propo : str, optional
            Name of the Propofol PK Model. The default is 'Schnider'.
        model_remi : str, optional
            Name of the Remifentanil PK Model. The default is 'Minto'.
        ts : float, optional
            Samplling time (s). The default is 1.
        BIS_param : list, optional
            Parameter of the BIS model (Propo Remi interaction)
            list [C50p_BIS, C50r_BIS, gamma_BIS, beta_BIS, E0_BIS, Emax_BIS].
            The default is None.
        random_PK : bool, optional
            Add uncertainties in the Propodfol and Remifentanil PK models. The default is False.
        random_PD : bool, optional
            Add uncertainties in the BIS PD model. The default is False.
        co_update : bool, optional
            Turn on the option to update PK parameters thanks to the CO value. The default is False.
        save_data_bool : bool, optional
            Save all interns variable at each sampling time in a data frame. The default is True.

        Returns
        -------
        None.

        """
        self.age = patient_characteristic[0]
        self.height = patient_characteristic[1]
        self.weight = patient_characteristic[2]
        self.gender = patient_characteristic[3]
        self.co_base = co_base
        self.map_base = map_base
        self.ts = ts
        self.model_propo = model_propo
        self.model_remi = model_remi
        self.hill_param = hill_param
        self.random_PK = random_PK
        self.random_PD = random_PD
        self.co_update = co_update
        self.save_data_bool = save_data_bool

        # LBM computation
        if self.gender == 1:  # homme
            self.lbm = 1.1 * self.weight - 128 * (self.weight / self.height) ** 2
        elif self.gender == 0:  # femme
            self.lbm = 1.07 * self.weight - 148 * (self.weight / self.height) ** 2

        # Init PK models for all drugs
        self.propo_pk = CompartmentModel(patient_characteristic, self.lbm, drug="Propofol",
                                         ts=self.ts, model=model_propo, random=random_PK)

        self.remi_pk = CompartmentModel(patient_characteristic, self.lbm, drug="Remifentanil",
                                        ts=self.ts, model=model_remi, random=random_PK)

        self.nore_pk = CompartmentModel(patient_characteristic, self.lbm, drug="Norepinephrine",
                                        ts=self.ts, model=model_remi, random=random_PK)

        # Init PD model for BIS
        self.bis_pd = BIS_model(hill_model='Bouillon', hill_param=hill_param, random=random_PD)
        self.hill_param = self.bis_pd.hill_param

        # Init PD model for TOL
        self.tol_pd = TOL_model(model='Bouillon', random=random_PD)

        # Init PD model for Hemodynamic
        self.hemo_pd = Hemo_PD_model(random=random_PD, co_base=co_base, map_base=map_base)

        # init blood loss volume
        self.blood_volume = self.propo_pk.v1
        self.blood_volume_init = self.propo_pk.v1

        # Init all the output variable
        self.bis = self.bis_pd.compute_bis(0, 0)
        self.tol = self.tol_pd.compute_tol(0, 0)
        self.map = map_base
        self.co = co_base

        # Save data
        if self.save_data_bool:
            # Time variable which will be stored
            self.Time = 0
            column_names = ['Time',  # time
                            'BIS', 'TOL', 'MAP', 'CO',  # outputs
                            'u_propo', 'u_remi', 'u_nore',  # inputs
                            'x_propo_1', 'x_propo_2', 'x_propo_3', 'x_propo_4', 'x_propo_5', 'x_propo_6',  # x_PK_propo
                            'x_remi_1', 'x_remi_2', 'x_remi_3', 'x_remi_4', 'x_remi_5',  # x_PK_remi
                            'c_blood_nore', 'v_blood']  # nore concentration and blood volume

            self.dataframe = pd.DataFrame(columns=column_names)

    def one_step(self, u_propo: float = 0, u_remi: float = 0, u_nore: float = 0,
                 blood_rate: float = 0, Dist: list = [0]*3, noise: bool = True) -> list:
        """
        Simulate one step time of the patient.

        Parameters
        ----------
        u_propo : float, optional
            Propofol infusion rate (mg/s). The default is 0.
        u_remi : float, optional
            Remifentanil infusion rate (µg/s). The default is 0.
        u_nore : float, optional
            Norepinephrine infusion rate (µg/s). The default is 0.
        blood_rate : float, optional
            Fluid rates from blood volume (mL/min), negative is bleeding while positive is a transfusion.
            The default is 0.
        Dist : list, optional
            Disturbance vector on [BIS (%), MAP (mmHg), CO (L/min)]. The default is [0]*3.
        noise : bool, optional
            bool to add measurement noise on the outputs. The default is True.

        Returns
        -------
        output : list
            [BIS, MAP, CO, TOL] : current BIS (%), MAP (mmHg) ,and CO (L/min), TOL (%)

        """
        # compute PK model
        self.c_es_propo = self.propo_pk.one_step(u_propo)
        self.c_es_remi = self.remi_pk.one_step(u_remi)
        self.c_blood_nore = self.nore_pk.one_step(u_nore)
        # BIS
        self.bis = self.bis_pd.compute_bis(self.c_es_propo, self.c_es_remi)
        # TOL
        self.tol = self.tol_pd.compute_tol(self.c_es_propo, self.c_es_remi)
        # Hemodynamic
        self.map, self.co = self.hemo_pd.compute_hemo(self.propo_pk.x[4:], self.remi_pk.x[4], self.c_blood_nore)
        # disturbances
        self.bis += Dist[0]
        self.map += Dist[1]
        self.co += Dist[2]

        # blood loss effect
        if blood_rate != 0 or self.blood_volume != self.blood_volume_init:
            self.blood_loss(blood_rate)
            self.map *= self.blood_volume/self.blood_volume_init
            self.co *= self.blood_volume/self.blood_volume_init

        # update PK model with CO
        if self.co_update:
            self.propo_pk.update_param_CO(self.co/self.co_base)
            self.remi_pk.update_param_CO(self.co/self.co_base)
            self.nore_pk.update_param_CO(self.co/self.co_base)

        # add noise
        if noise:
            self.bis += np.random.normal(scale=3)
            self.map += np.random.normal(scale=0.5)
            self.co += np.random.normal(scale=0.1)

        # Save data
        if self.save_data_bool:
            self.save_data([u_propo, u_remi, u_nore])

        return([self.bis, self.co, self.map, self.tol])

    def find_equilibrium(self, bis_target: float, tol_target: float, map_target: float) -> list:
        """
        Find the input to meet the targeted outputs at the equilibrium.

        Parameters
        ----------
        bis_target : float
            BIS target (%).
        tol_target : float
            TOL target ([0, 1]).
        map_target:float
            MAP target (mmHg).

        Returns
        -------
        list
            list of input [up, ur, ud, us, ua] with the respective units [mg/s, µg/s, µg/s, µg/s, µg/s].

        """
        # find Remifentanil and Propofol Concentration from BIS and TOL
        cep = cas.MX.sym('cep')  # effect site concentration of propofol in the optimization problem
        cer = cas.MX.sym('cer')  # effect site concentration of remifentanil in the optimization problem

        bis = self.bis_pd.compute_bis(cep, cer)
        tol = self.tol_pd.compute_tol(cep, cer)

        J = (bis - bis_target)**2/100**2 + (tol - tol_target)**2 + 0.00001 * (cep*2-cer)**2
        w = [cep, cer]
        w0 = [self.bis_pd.c50p, self.bis_pd.c50r/2.5]
        lbw = [0, 0]
        ubw = [50, 50]

        opts = {'ipopt.print_level': 0, 'print_time': 0}
        prob = {'f': J, 'x': cas.vertcat(*w)}
        solver = cas.nlpsol('solver', 'ipopt', prob, opts)
        sol = solver(x0=w0, lbx=lbw, ubx=ubw)
        w_opt = sol['x'].full().flatten()
        self.c_blood_propo_eq = w_opt[0]
        self.c_blood_remi_eq = w_opt[1]

        # get Norepinephrine rate from MAP target
        # first compute the effect of propofol and remifentanil on MAP
        map_without_nore, co_without_nore = self.hemo_pd.compute_hemo([self.c_blood_propo_eq, self.c_blood_propo_eq],
                                                                      self.c_blood_remi_eq, 0)
        # Then compute the right nore concentration to meet the MAP target
        wanted_map_effect = map_target - map_without_nore
        self.c_blood_nore_eq = self.hemo_pd.c50_nore_map * (wanted_map_effect /
                                                            (self.hemo_pd.emax_nore_map-wanted_map_effect)
                                                            )**(1/self.hemo_pd.gamma_nore_map)
        _, self.co_eq = self.hemo_pd.compute_hemo([self.c_blood_propo_eq, self.c_blood_propo_eq],
                                                  self.c_blood_remi_eq, self.c_blood_nore_eq)
        # update pharmacokinetics model from co value
        if self.co_update:
            self.propo_pk.update_param_CO(self.co_eq/self.co_base)
            self.remi_pk.update_param_CO(self.co_eq/self.co_base)
            self.nore_pk.update_param_CO(self.co_eq/self.co_base)
        # get rate input
        self.u_propo_eq = self.c_blood_propo_eq / control.dcgain(self.propo_pk.continuous_sys)
        self.u_remi_eq = self.c_blood_remi_eq / control.dcgain(self.remi_pk.continuous_sys)
        self.u_nore_eq = self.c_blood_nore_eq / control.dcgain(self.nore_pk.continuous_sys)

        return self.u_propo_eq, self.u_remi_eq, self.u_nore_eq

    def initialized_at_given_input(self, u_propo: float = 0, u_remi: float = 0, u_nore: float = 0):
        """
        Initialize the patient Simulator at the given input as an equilibrium point.

        Parameters
        ----------
        u_propo : float, optional
            Propofol infusion rate (mg/s). The default is 0.
        u_remi : float, optional
            Remifentanil infusion rate (µg/s). The default is 0.
        u_nore : float, optional
            Norepinephrine infusion rate (µg/s). The default is 0.

        Returns
        -------
        None.

        """
        self.u_propo_eq = u_propo
        self.u_remi_eq = u_remi
        self.u_nore_eq = u_nore

        self.c_blood_propo_eq = u_propo * control.dcgain(self.propo_pk.continuous_sys)
        self.c_blood_remi_eq = u_remi * control.dcgain(self.remi_pk.continuous_sys)
        self.c_blood_remi_eq = u_nore * control.dcgain(self.nore_pk.continuous_sys)

        # PK models
        x_init_propo = np.linalg.solve(-self.propo_pk.continuous_sys.A, self.propo_pk.continuous_sys.B * u_propo)
        self.propo_pk.x = x_init_propo

        x_init_remi = np.linalg.solve(-self.remi_pk.continuous_sys.A, self.remi_pk.continuous_sys.B * u_remi)
        self.remi_pk.x = x_init_remi

        x_init_nore = np.linalg.solve(-self.nore_pk.continuous_sys.A, self.nore_pk.continuous_sys.B * u_nore)
        self.nore_pk.x = x_init_nore

    def initialized_at_maintenance(self, bis_target: float, tol_target: float, map_target: float):
        """Initialize the patient model at the equilibrium point for the given output value.

        Parameters
        ----------
        bis_target : float
            BIS target (%).
        rass_target : float
            RASS target ([0, -5]).
        map_target:float
            MAP target (mmHg).

        Returns
        -------
        None.

        """
        # Find equilibrium point

        self.find_equilibrium(bis_target, tol_target, map_target)

        # set them as starting point in the simulator

        self.initialized_at_given_input(u_propo=self.u_propo_eq,
                                        u_remi=self.u_remi_eq,
                                        u_nore=self.u_nore_eq)

    def blood_loss(self, fluid_rate: float = 0):
        """Actualize the patient parameters to mimic blood loss.

        Parameters
        ----------
        fluid_rate : float, optional
            Fluid rates from blood volume (mL/min), negative is bleeding while positive is a transfusion.
            The default is 0.

        Returns
        -------
        None.

        """
        fluid_rate = fluid_rate/1000 / 60  # in L/s
        # compute the blood volume
        self.blood_volume += fluid_rate*self.ts

        # Update the models
        self.propo_pk.update_param_blood_loss(self.blood_volume/self.blood_volume_init)
        self.remi_pk.update_param_blood_loss(self.blood_volume/self.blood_volume_init)
        self.nore_pk.update_param_blood_loss(self.blood_volume/self.blood_volume_init)
        self.bis_pd.update_param_blood_loss(self.blood_volume/self.blood_volume_init)

    def save_data(self, inputs: list = [0, 0, 0]):
        """Save all current intern variable as a new line in self.dataframe."""
        # compute time
        self.Time += self.ts
        # store data

        new_line = {'Time': self.Time,
                    'BIS': self.bis, 'TOL': self.tol, 'MAP': self.map, 'CO': self.co,  # outputs
                    'u_propo': inputs[0], 'u_remi': inputs[1], 'u_nore': inputs[2],  # inputs
                    'c_blood_nore': self.c_blood_nore, 'v_blood': self.blood_volume}  # concentration and blood volume

        line_x_propo = {'x_propo_' + str(i+1): self.propo_pk.x[i] for i in range(6)}
        line_x_remi = {'x_remi_' + str(i+1): self.remi_pk.x[i] for i in range(5)}
        new_line.update(line_x_propo)
        new_line.update(line_x_remi)

        self.dataframe = pd.concat((self.dataframe, pd.DataFrame(new_line)), ignore_index=True)