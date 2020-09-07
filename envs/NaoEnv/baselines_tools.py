#!/usr/bin/env python3
import sys
try:
    sys.path.remove('/opt/ros/kinetic/lib/python2.7/dist-packages')
except Exception:
    pass

from nao_env import NaoEnv
from nao_env_pretrained import NaoEnvPretrained

import numpy as np
from datetime import datetime
import time

import tensorflow as tf
from stable_baselines.common.policies import MlpPolicy
from stable_baselines.ddpg.policies import LnMlpPolicy as DDPGMlpPolicy
from stable_baselines.common.vec_env import SubprocVecEnv, DummyVecEnv
from stable_baselines import PPO2
from stable_baselines import GAIL
from stable_baselines.ddpg.noise import OrnsteinUhlenbeckActionNoise
from stable_baselines import DDPG
from stable_baselines.gail import generate_expert_traj
from stable_baselines.gail import ExpertDataset
from stable_baselines.common import set_global_seeds
from stable_baselines.ddpg.policies import FeedForwardPolicy as DDPGFeedForwardPolicy
from stable_baselines.common.policies import FeedForwardPolicy as COMMONFeedForwardPolicy


ENV_ID = 'NaoEnv'
ENV_ID_PRETRAINED = 'NaoEnvPretrained'
PATH_MODEL = 'models/models_nao/'
PATH_PRETRAINED = 'pretrain/pretrain_nao/'
AGENT = "PPO2"
LOG_PATH = "logs/nao_env/"
MODEL_NAME = "walk_pretrained"


class CustomDDPG(DDPGFeedForwardPolicy):
    def __init__(self, *args, **kwargs):
        super(CustomDDPG, self).__init__(*args, **kwargs,
                                         layers=[1024, 512],
                                         feature_extraction="mlp")


class CustomCOMMON(COMMONFeedForwardPolicy):
    def __init__(self, *args, **kwargs):
        super(CustomCOMMON, self).__init__(*args, **kwargs,
                                           layers=[1024, 512, 512, 64],
                                           feature_extraction="mlp")


def make_env(rank, seed=0):
    """
    Utility function for multiprocessed env.

    :param num_env: (int) the number of environments you wish to have in subpro
    :param seed: (int) the inital seed for RNG
    :param rank: (int) index of the subprocess
    """
    def _init():
        env = NaoEnv(gui=False)
        env.seed(seed + rank)
        time.sleep(0.1)
        return env
    set_global_seeds(seed)
    return _init


def init_model(gui=True, dataset=None, num_env=4):
    env = None
    if not gui and AGENT != "DDPG" and AGENT == "GAIL":
        env = SubprocVecEnv([make_env(i) for i in range(num_env)])
    else:
        env = globals()[ENV_ID](gui=gui)
        env = DummyVecEnv([lambda:env])
    if AGENT is "PPO2":
        model = PPO2(
                 CustomCOMMON,
                 env,
                 verbose=2,
                 tensorboard_log=LOG_PATH + AGENT + "Agent/" +
                 datetime.now().strftime(
                     "%Y%m%d-%H%M%S"))
    if AGENT is "DDPG":
        action_noise = OrnsteinUhlenbeckActionNoise(
                    mean=np.zeros(env.action_space.shape[-1]),
                    sigma=float(0.5) * np.ones(env.action_space.shape[-1]))
        model = DDPG(
            CustomDDPG,
            env,
            verbose=2,
            param_noise=None,
            action_noise=action_noise,
            tensorboard_log=LOG_PATH + AGENT + "Agent/" +
            datetime.now().strftime("%Y%m%d-%H%M%S"))
    if AGENT is "GAIL":
        if dataset is None:
            return -1
        model = GAIL(CustomCOMMON, env, dataset, verbose=2,
                     tensorboard_log=LOG_PATH + AGENT + "Agent/" +
                     datetime.now().strftime("%Y%m%d-%H%M%S"))
    return env, model


def train(num_timesteps, seed, model_path=None):
    dataset = ExpertDataset(
                    expert_path=PATH_PRETRAINED + MODEL_NAME + '.npz',
                    traj_limitation=-1, verbose=1, batch_size=32,
                    randomize=False)
    env, model = init_model(dataset=dataset, gui=True)
    try:
        model.learn(total_timesteps=num_timesteps, reset_num_timesteps=False)
    except KeyboardInterrupt:
        print("Program Interrupted")
        pass
    model.save(model_path + "/" + AGENT + "_" + MODEL_NAME)
    env.close()


def collect_pretrained_dataset(dataset_name):
    env = globals()[ENV_ID_PRETRAINED](gui=True)
    generate_expert_traj(env.walking_expert_position,
                         PATH_PRETRAINED + dataset_name,
                         env, n_episodes=40)
    env.close()


def pretrained_model(dataset_name, model):
    dataset = ExpertDataset(expert_path=dataset_name + '.npz',
                            traj_limitation=-1)
    model.pretrain(dataset, n_epochs=1000)
    return model


def pretrained_model_and_save(dataset_name):
    env, model = init_model(gui=False)
    model = pretrained_model(PATH_PRETRAINED + dataset_name, model)
    model.save(PATH_MODEL + AGENT + "_" + dataset_name)
    env.close()


def visualize(name_model):
    model = getattr(globals()[AGENT], 'load')(name_model, policy=CustomCOMMON)
    env = globals()[ENV_ID](gui=True)
    env = DummyVecEnv([lambda: env])
    # Enjoy trained agent
    obs = env.reset()
    while True:
        action, _states = model.predict(obs)
        obs, _, _, _ = env.step(action)
        env.render()
